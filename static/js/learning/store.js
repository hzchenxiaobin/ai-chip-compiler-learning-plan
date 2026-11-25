/**
 * store.js — IndexedDB 存储与本地数据管理（WP-04/WP-06）。
 *
 * 对应 docs/development/02_前端学习模块.md §3—§7：
 * - IndexedDB v1（progress/meta）+ 内存降级 Store（同一接口）
 * - 事务安全：put 成功 ≠ 保存成功，oncomplete 才算提交
 * - 导入两阶段：完整预检（不写库）→ 用户确认后单事务写入
 * - revision 整记录合并；替换模式先备份再替换，事务 abort 全回滚
 * - BroadcastChannel 跨标签失效通知（localStorage 兜底）
 *
 * UI 不直接访问原生 IDBRequest；本模块不操作 DOM。
 */

import { normalizeTasks, createDayProgress } from './progress.js';

export const DB_NAME = 'ai-chip-compiler-learning';
export const DB_VERSION = 1;
export const EXPORT_KIND = 'ai-chip-compiler-learning-progress';
export const IMPORT_MAX_BYTES = 5 * 1024 * 1024;
export const IMPORT_MAX_RECORDS = 500;
export const UI_PREFS_KEY = 'learning.ui.v1';

const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
const SHA_RE = /^[0-9a-f]{64}$/;
const TS_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;
const TASK_STATUSES = new Set(['not_started', 'in_progress', 'done', 'blocked', 'not_applicable']);
const TASK_IDS = ['reading', 'exercise', 'experiment', 'acceptance'];

export class StoreError extends Error {
  constructor(code, message) {
    super(`[${code}] ${message}`);
    this.code = code;
  }
}

function nowIso() {
  return new Date().toISOString();
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function transactionDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new StoreError('STORAGE_UNAVAILABLE', '事务被中止'));
  });
}

/** 规范化记录内容（用于“同 revision 内容是否相同”比较与冲突检测）。 */
export function canonicalRecord(record) {
  const tasks = {};
  for (const taskId of TASK_IDS) {
    const task = record.tasks && record.tasks[taskId];
    if (task && TASK_STATUSES.has(task.status)) {
      tasks[taskId] = { status: task.status, updated_at: task.updated_at || '' };
    }
  }
  return {
    content_sha: record.content_sha || '',
    planned: !!record.planned,
    tasks,
    latest_evidence_id: record.latest_evidence_id || null,
    stuck_item_ids: Array.isArray(record.stuck_item_ids) ? record.stuck_item_ids.slice() : [],
    last_visited_at: record.last_visited_at || '',
    needs_review: !!record.needs_review,
    revision: typeof record.revision === 'number' ? record.revision : 0,
  };
}

// ---------------------------------------------------------------------------
// 打开与升级
// ---------------------------------------------------------------------------

let broadcastChannel = null;
try {
  broadcastChannel = new BroadcastChannel('learning-progress-v1');
} catch (err) {
  broadcastChannel = null;
}

function notifyInvalidation(dayIds) {
  const message = JSON.stringify({ type: 'invalidate', day_ids: dayIds || null });
  if (broadcastChannel) {
    try {
      broadcastChannel.postMessage(message);
    } catch (err) {
      /* 通道关闭时忽略 */
    }
  }
  try {
    localStorage.setItem('learning-storage-event', String(Date.now()) + ':' + message.length);
  } catch (err) {
    /* 隐私模式下忽略 */
  }
}

export function openStore() {
  return new Promise((resolve) => {
    if (typeof indexedDB === 'undefined') {
      resolve(new MemoryStore());
      return;
    }
    let request;
    try {
      request = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (err) {
      resolve(new MemoryStore());
      return;
    }
    const openTimeout = setTimeout(() => {
      try {
        request && request.source && request.abort && request.abort();
      } catch (err) {
        /* 忽略 */
      }
      resolve(new MemoryStore());
    }, 8000);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('progress')) {
        const progress = db.createObjectStore('progress', { keyPath: 'day_id' });
        progress.createIndex('last_visited_at', 'last_visited_at', { unique: false });
      }
      if (!db.objectStoreNames.contains('meta')) {
        db.createObjectStore('meta', { keyPath: 'key' });
      }
    };
    request.onsuccess = () => {
      clearTimeout(openTimeout);
      const db = request.result;
      db.onversionchange = () => db.close();
      resolve(new IdbStore(db));
    };
    request.onerror = () => {
      clearTimeout(openTimeout);
      resolve(new MemoryStore());
    };
    request.onblocked = () => {
      clearTimeout(openTimeout);
      resolve(new MemoryStore());
    };
  });
}

// ---------------------------------------------------------------------------
// 持久化 Store（IndexedDB）
// ---------------------------------------------------------------------------

class IdbStore {
  constructor(db) {
    this._db = db;
    this._listeners = new Set();
    this._queue = Promise.resolve();
    this.isPersistent = true;
    if (broadcastChannel) {
      broadcastChannel.onmessage = () => this._emit(null);
    }
    try {
      window.addEventListener('storage', (event) => {
        if (event.key === 'learning-storage-event') this._emit(null);
      });
    } catch (err) {
      /* 非 window 环境（测试）忽略 */
    }
  }

  _emit(dayIds) {
    for (const listener of this._listeners) {
      try {
        listener(dayIds);
      } catch (err) {
        /* 单个监听器失败不影响其他 */
      }
    }
  }

  onChange(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  /** 同页串行队列：保证点击顺序，避免并发事务交错。 */
  _enqueue(operation) {
    const next = this._queue.then(operation, operation);
    this._queue = next.catch(() => {});
    return next;
  }

  getDay(dayId) {
    return this._enqueue(() =>
      requestToPromise(this._db.transaction('progress', 'readonly').objectStore('progress').get(dayId))
    );
  }

  getAllDays() {
    return this._enqueue(() =>
      requestToPromise(this._db.transaction('progress', 'readonly').objectStore('progress').getAll())
    );
  }

  putDay(record) {
    return this.updateDay(record.day_id, () => record);
  }

  /** readwrite 事务内读取最新记录 → 同步 mutator → 写回；revision 由本方法统一 +1。 */
  updateDay(dayId, mutator) {
    return this._enqueue(
      () =>
        new Promise((resolve, reject) => {
          const tx = this._db.transaction('progress', 'readwrite');
          const store = tx.objectStore('progress');
          const getRequest = store.get(dayId);
          getRequest.onsuccess = () => {
            const base = getRequest.result || null;
            let next;
            try {
              next = mutator(base);
            } catch (err) {
              tx.abort();
              reject(err);
              return;
            }
            if (!next) {
              resolve(null);
              return;
            }
            next.revision = base && typeof base.revision === 'number' ? base.revision + 1 : next.revision || 0;
            const putRequest = store.put(next);
            putRequest.onerror = () => reject(putRequest.error);
          };
          getRequest.onerror = () => reject(getRequest.error);
          transactionDone(tx)
            .then(() => {
              notifyInvalidation([dayId]);
              this._emit([dayId]);
              resolve(true);
            })
            .catch(reject);
        })
    );
  }

  async clearProgress() {
    await this._enqueue(
      () =>
        new Promise((resolve, reject) => {
          const tx = this._db.transaction('progress', 'readwrite');
          tx.objectStore('progress').clear();
          transactionDone(tx).then(resolve, reject);
        })
    );
    const remaining = await this.getAllDays();
    if (remaining.length !== 0) {
      throw new StoreError('STORAGE_UNAVAILABLE', '清空后仍有残留记录');
    }
    notifyInvalidation(null);
    this._emit(null);
  }

  async exportProgress(days) {
    const records = await this.getAllDays();
    const byId = new Map(records.map((r) => [r.day_id, r]));
    const ordered = (days || records.map((r) => ({ day_id: r.day_id })))
      .map((day) => byId.get(day.day_id))
      .filter(Boolean)
      .map((record) => ({ ...canonicalRecord(record), schema_version: 1, day_id: record.day_id }));
    const payload = {
      schema_version: 1,
      kind: EXPORT_KIND,
      exported_at: nowIso(),
      content_commit: (typeof globalThis.__LEARNING_CONTENT_COMMIT__ === 'string' && globalThis.__LEARNING_CONTENT_COMMIT__) || '',
      days: ordered,
    };
    return new Blob([JSON.stringify(payload, null, 2) + '\n'], { type: 'application/json' });
  }

  async getMeta(key) {
    return this._enqueue(() =>
      requestToPromise(this._db.transaction('meta', 'readonly').objectStore('meta').get(key))
    );
  }

  close() {
    try {
      this._db.close();
    } catch (err) {
      /* 已关闭时忽略 */
    }
  }
}

// ---------------------------------------------------------------------------
// 内存降级 Store（同一接口；isPersistent=false，刷新即失）
// ---------------------------------------------------------------------------

class MemoryStore {
  constructor() {
    this._records = new Map();
    this._meta = new Map();
    this._listeners = new Set();
    this.isPersistent = false;
  }

  _emit(dayIds) {
    for (const listener of this._listeners) {
      try {
        listener(dayIds);
      } catch (err) {
        /* 忽略单个监听器失败 */
      }
    }
  }

  onChange(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  async getDay(dayId) {
    return this._records.get(dayId) || null;
  }

  async getAllDays() {
    return [...this._records.values()].map((record) => ({ ...record }));
  }

  async updateDay(dayId, mutator) {
    const base = this._records.get(dayId) || null;
    const next = mutator(base);
    if (!next) return null;
    next.revision = base && typeof base.revision === 'number' ? base.revision + 1 : next.revision || 0;
    this._records.set(dayId, next);
    this._emit([dayId]);
    return true;
  }

  async putDay(record) {
    return this.updateDay(record.day_id, () => record);
  }

  async clearProgress() {
    this._records.clear();
    this._emit(null);
  }

  async exportProgress(days) {
    const records = await this.getAllDays();
    const byId = new Map(records.map((r) => [r.day_id, r]));
    const ordered = (days || records.map((r) => ({ day_id: r.day_id })))
      .map((day) => byId.get(day.day_id))
      .filter(Boolean)
      .map((record) => ({ ...canonicalRecord(record), schema_version: 1, day_id: record.day_id }));
    const payload = {
      schema_version: 1,
      kind: EXPORT_KIND,
      exported_at: nowIso(),
      content_commit: (typeof globalThis.__LEARNING_CONTENT_COMMIT__ === 'string' && globalThis.__LEARNING_CONTENT_COMMIT__) || '',
      days: ordered,
    };
    return new Blob([JSON.stringify(payload, null, 2) + '\n'], { type: 'application/json' });
  }

  async getMeta(key) {
    return this._meta.get(key) || null;
  }

  close() {}
}

// ---------------------------------------------------------------------------
// 导入：阶段 A 完整预检（不写库）
// ---------------------------------------------------------------------------

function detectDuplicateKeys(text) {
  // 轻量重复键检测：逐对象扫描原始文本中的键名序列
  const errors = [];
  const objectRegex = /\{([^{}]*)\}/g;
  let match;
  while ((match = objectRegex.exec(text)) !== null) {
    const body = match[1];
    const keyRegex = /"((?:[^"\\]|\\.)*)"\s*:/g;
    const seen = new Set();
    let keyMatch;
    while ((keyMatch = keyRegex.exec(body)) !== null) {
      if (seen.has(keyMatch[1])) {
        errors.push(keyMatch[1]);
        break;
      }
      seen.add(keyMatch[1]);
    }
  }
  return errors;
}

function validateImportedRecord(raw, day, index) {
  const where = `days[${index}]`;
  if (!raw || typeof raw !== 'object') {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：记录必须是对象`);
  }
  const knownFields = new Set([
    'schema_version', 'day_id', 'content_sha', 'planned', 'tasks',
    'latest_evidence_id', 'stuck_item_ids', 'last_visited_at', 'needs_review', 'revision',
  ]);
  const unknownFields = Object.keys(raw).filter((key) => !knownFields.has(key) && !DANGEROUS_KEYS.has(key));
  if (raw.day_id !== day.day_id) {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：day_id ${raw.day_id} 与目录不一致`);
  }
  if (typeof raw.content_sha !== 'string' || !SHA_RE.test(raw.content_sha)) {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：content_sha 必须是 64 位小写十六进制`);
  }
  if (typeof raw.planned !== 'boolean') {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：planned 必须是布尔值`);
  }
  if (!raw.tasks || typeof raw.tasks !== 'object') {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：tasks 缺失`);
  }
  for (const taskId of Object.keys(raw.tasks)) {
    if (!TASK_IDS.includes(taskId)) {
      throw new StoreError('DATA_SCHEMA_INVALID', `${where}：未知任务 ${taskId}`);
    }
    const task = raw.tasks[taskId];
    if (!task || !TASK_STATUSES.has(task.status)) {
      throw new StoreError('DATA_SCHEMA_INVALID', `${where}：tasks.${taskId}.status 非法`);
    }
    if (typeof task.updated_at !== 'string' || !TS_RE.test(task.updated_at)) {
      throw new StoreError('DATA_SCHEMA_INVALID', `${where}：tasks.${taskId}.updated_at 时间戳非法`);
    }
  }
  if (raw.latest_evidence_id !== null && typeof raw.latest_evidence_id !== 'string') {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：latest_evidence_id 必须为 null 或字符串`);
  }
  if (!Array.isArray(raw.stuck_item_ids) || raw.stuck_item_ids.some((id) => typeof id !== 'string')) {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：stuck_item_ids 必须是字符串数组`);
  }
  if (typeof raw.last_visited_at !== 'string' || !TS_RE.test(raw.last_visited_at)) {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：last_visited_at 时间戳非法`);
  }
  if (typeof raw.needs_review !== 'boolean') {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：needs_review 必须是布尔值`);
  }
  if (typeof raw.revision !== 'number' || !Number.isInteger(raw.revision) || raw.revision < 0 || raw.revision > 2147483647) {
    throw new StoreError('DATA_SCHEMA_INVALID', `${where}：revision 必须是 0—2147483647 的整数`);
  }
  const tasks = normalizeTasks(day.type, raw.tasks, raw.last_visited_at);
  const record = {
    schema_version: 1,
    day_id: day.day_id,
    content_sha: raw.content_sha,
    planned: raw.planned,
    tasks,
    latest_evidence_id: raw.latest_evidence_id || null,
    stuck_item_ids: raw.stuck_item_ids.slice(),
    last_visited_at: raw.last_visited_at,
    needs_review: raw.needs_review,
    revision: raw.revision,
  };
  return { record, unknownFields };
}

/**
 * 阶段 A：完整预检导入文件，不写任何数据。
 * 返回 {ok, errors, summary, entries}；entries[].action ∈
 * new | update | skip | unchanged | conflict | unknown_day。
 */
export async function precheckImport(file, days) {
  if (file && typeof file.size === 'number' && file.size > IMPORT_MAX_BYTES) {
    throw new StoreError('DATA_SCHEMA_INVALID', `文件超过 ${IMPORT_MAX_BYTES} 字节上限`);
  }
  const text = await file.text();
  if (text.startsWith('\ufeff')) {
    throw new StoreError('DATA_SCHEMA_INVALID', '文件带有 BOM，请另存为无 BOM 的 UTF-8');
  }
  const duplicateKeys = detectDuplicateKeys(text);
  if (duplicateKeys.length) {
    throw new StoreError('DATA_SCHEMA_INVALID', `JSON 存在重复键：${duplicateKeys[0]}`);
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new StoreError('DATA_SCHEMA_INVALID', `JSON 解析失败：${err.message}`);
  }
  if (data && typeof data === 'object') {
    for (const key of Object.keys(data)) {
      if (DANGEROUS_KEYS.has(key)) {
        throw new StoreError('DATA_SCHEMA_INVALID', `导入包含危险键：${key}`);
      }
    }
  }
  if (!data || typeof data !== 'object' || data.schema_version === undefined) {
    throw new StoreError('DATA_SCHEMA_INVALID', '缺少 schema_version');
  }
  if (data.schema_version !== 1) {
    throw new StoreError('DATA_VERSION_UNSUPPORTED', `不支持的 schema_version：${data.schema_version}`);
  }
  if (data.kind !== EXPORT_KIND) {
    throw new StoreError('DATA_SCHEMA_INVALID', `kind 必须为 ${EXPORT_KIND}`);
  }
  if (!Array.isArray(data.days)) {
    throw new StoreError('DATA_SCHEMA_INVALID', 'days 必须是数组');
  }
  if (data.days.length > IMPORT_MAX_RECORDS) {
    throw new StoreError('DATA_SCHEMA_INVALID', `记录数超过上限 ${IMPORT_MAX_RECORDS}`);
  }

  const daysById = new Map(days.map((day) => [day.day_id, day]));
  const entries = [];
  const errors = [];
  const seen = new Set();
  let unknownFieldsCount = 0;
  const unknownDays = [];
  for (let index = 0; index < data.days.length; index += 1) {
    const raw = data.days[index];
    const dayId = raw && raw.day_id;
    if (seen.has(dayId)) {
      errors.push(`days[${index}]：${dayId} 重复出现`);
      continue;
    }
    seen.add(dayId);
    const day = daysById.get(dayId);
    if (!day) {
      unknownDays.push(dayId);
      entries.push({ dayId: String(dayId), action: 'unknown_day', incoming: null });
      continue;
    }
    try {
      const { record, unknownFields } = validateImportedRecord(raw, day, index);
      unknownFieldsCount += unknownFields.length;
      entries.push({ dayId, day, action: 'pending_records', incoming: record, unknownFields });
    } catch (err) {
      errors.push(err.message.replace(/^\[[A-Z_]+\]\s*/, ''));
    }
  }
  if (errors.length) {
    throw new StoreError('DATA_SCHEMA_INVALID', `预检失败（首个错误）：${errors[0]}；共 ${errors.length} 个`);
  }
  return { ok: true, entries, unknownDays, unknownFieldsCount, rawCount: data.days.length };
}

/** 结合本机现有记录把 pending_records 归类为 new/update/skip/unchanged/conflict。 */
export async function classifyImportEntries(store, plan) {
  const existing = new Map((await store.getAllDays()).map((record) => [record.day_id, record]));
  for (const entry of plan.entries) {
    if (entry.action !== 'pending_records') continue;
    const current = existing.get(entry.dayId);
    if (!current) {
      entry.action = 'new';
      continue;
    }
    const incomingCanonical = canonicalRecord(entry.incoming);
    const currentCanonical = canonicalRecord(current);
    if (entry.incoming.revision > current.revision) entry.action = 'update';
    else if (entry.incoming.revision < current.revision) entry.action = 'skip';
    else if (JSON.stringify(incomingCanonical) === JSON.stringify(currentCanonical)) entry.action = 'unchanged';
    else entry.action = 'conflict';
    entry.existing = current;
  }
  const summary = { new: 0, update: 0, skip: 0, unchanged: 0, conflict: 0, unknown_day: 0 };
  for (const entry of plan.entries) summary[entry.action] = (summary[entry.action] || 0) + 1;
  plan.summary = summary;
  plan.existingById = existing;
  return plan;
}

// ---------------------------------------------------------------------------
// 导入：阶段 B 单事务写入
// ---------------------------------------------------------------------------

/**
 * 应用导入计划。
 * options.mode ∈ merge | replace；options.resolutions: {dayId: 'local'|'incoming'|'later'}。
 * 返回 {added, updated, skipped, unchanged, conflictsPending, failed, mode}。
 */
export async function applyImport(store, plan, options) {
  const mode = options.mode === 'replace' ? 'replace' : 'merge';
  const resolutions = options.resolutions || {};
  const writes = [];
  const report = { added: 0, updated: 0, skipped: 0, unchanged: 0, conflictsPending: 0, failed: 0, mode };
  for (const entry of plan.entries) {
    if (entry.action === 'new' || entry.action === 'update') {
      writes.push(entry.incoming);
    } else if (entry.action === 'unchanged' || entry.action === 'skip' || entry.action === 'unknown_day') {
      report[entry.action === 'unknown_day' ? 'skipped' : entry.action] += 1;
    } else if (entry.action === 'conflict') {
      const choice = resolutions[entry.dayId];
      if (choice === 'incoming') writes.push(entry.incoming);
      else if (choice === 'local') report.unchanged += 1;
      else report.conflictsPending += 1;
    }
  }
  if (report.conflictsPending > 0 && mode === 'merge') {
    return report;
  }
  try {
    await store._runImportTransaction(writes, mode);
    report.added = writes.length;
  } catch (err) {
    report.failed = 1;
    report.error = err;
  }
  return report;
}

// IdbStore：单事务导入（替换模式先写备份，再清空，再写入；abort 全回滚）
IdbStore.prototype._runImportTransaction = function _runImportTransaction(writes, mode) {
  return this._enqueue(
    () =>
      new Promise((resolve, reject) => {
        const tx = this._db.transaction(['progress', 'meta'], 'readwrite');
        const progress = tx.objectStore('progress');
        const meta = tx.objectStore('meta');
        const afterCurrent = (currentRecords) => {
          if (mode === 'replace') {
            meta.put({
              key: 'last_pre_replace_backup',
              value: { created_at: nowIso(), days: currentRecords },
            });
            progress.clear();
          }
          for (const record of writes) progress.put(record);
        };
        if (mode === 'replace') {
          const getAllRequest = progress.getAll();
          getAllRequest.onsuccess = () => afterCurrent(getAllRequest.result);
          getAllRequest.onerror = () => reject(getAllRequest.error);
        } else {
          afterCurrent([]);
        }
        transactionDone(tx)
          .then(() => {
            notifyInvalidation(null);
            this._emit(null);
            resolve();
          })
          .catch(reject);
      })
  );
};

MemoryStore.prototype._runImportTransaction = async function _runImportTransaction(writes, mode) {
  const snapshot = [...this._records.values()].map((record) => ({ ...record }));
  try {
    if (mode === 'replace') {
      this._meta.set('last_pre_replace_backup', { key: 'last_pre_replace_backup', value: { created_at: nowIso(), days: snapshot } });
      this._records.clear();
    }
    for (const record of writes) this._records.set(record.day_id, record);
    this._emit(null);
  } catch (err) {
    this._records.clear();
    for (const record of snapshot) this._records.set(record.day_id, record);
    throw err;
  }
};

/** 从最近一次替换前备份恢复（不存在备份时报错）。 */
export async function restorePreReplaceBackup(store) {
  const backup = await store.getMeta('last_pre_replace_backup');
  if (!backup || !backup.value || !Array.isArray(backup.value.days)) {
    throw new StoreError('DATA_SCHEMA_INVALID', '没有可恢复的替换前备份');
  }
  await store._runImportTransaction(backup.value.days, 'replace');
  return backup.value.days.length;
}

// ---------------------------------------------------------------------------
// UI 偏好（localStorage，仅少量校验过的布尔/枚举）
// ---------------------------------------------------------------------------

export function getUiPrefs() {
  try {
    const raw = localStorage.getItem(UI_PREFS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const result = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (DANGEROUS_KEYS.has(key)) continue;
      if (typeof value === 'boolean' || typeof value === 'string' || typeof value === 'number') {
        result[key] = value;
      }
    }
    return result;
  } catch (err) {
    return {};
  }
}

export function setUiPrefs(prefs) {
  try {
    localStorage.setItem(UI_PREFS_KEY, JSON.stringify(prefs));
  } catch (err) {
    /* 配额或隐私模式：静默失败，不影响学习记录 */
  }
}

/** 只清除明确列出的 UI 偏好键，不调用 localStorage.clear()。 */
export function clearUiPrefs() {
  const cleared = [];
  try {
    localStorage.removeItem(UI_PREFS_KEY);
    cleared.push(UI_PREFS_KEY);
  } catch (err) {
    /* 忽略 */
  }
  try {
    if (localStorage.getItem('vp-theme') !== null) {
      localStorage.removeItem('vp-theme');
      cleared.push('vp-theme');
    }
  } catch (err) {
    /* 忽略 */
  }
  return cleared;
}




