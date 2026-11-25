/**
 * progress.js — 纯函数状态机与派生规则（WP-04）。
 *
 * 对应 docs/development/02_前端学习模块.md §2：
 * - 常量：TASK_IDS / TASK_STATUSES / DAY_STATES
 * - 类型 → 适用任务；四项子状态 → 整体状态
 * - 内容版本复核、计划当前日、周/阶段汇总、继续学习
 *
 * 本模块不得包含 DOM、存储或网络副作用；所有更新函数返回新对象。
 */

export const TASK_IDS = Object.freeze(['reading', 'exercise', 'experiment', 'acceptance']);

export const TASK_STATUSES = new Set([
  'not_started',
  'in_progress',
  'done',
  'blocked',
  'not_applicable',
]);

export const DAY_STATES = Object.freeze({
  NOT_STARTED: 'not_started',
  IN_PROGRESS: 'in_progress',
  READY_FOR_REVIEW: 'ready_for_review',
  COMPLETED: 'completed',
  BLOCKED: 'blocked',
});

const TYPE_TASKS = Object.freeze({
  concept_lab: ['reading', 'exercise', 'experiment', 'acceptance'],
  environment_lab: ['reading', 'exercise', 'experiment', 'acceptance'],
  integration: ['reading', 'exercise', 'experiment', 'acceptance'],
  review: ['reading', 'exercise', 'acceptance'],
  documentation: ['reading', 'exercise', 'acceptance'],
  presentation: ['reading', 'exercise', 'acceptance'],
  final_assessment: ['reading', 'exercise', 'experiment', 'acceptance'],
});

const TASK_LABELS = Object.freeze({
  reading: '阅读',
  exercise: '练习',
  experiment: '实验',
  acceptance: '验收',
});

const STATE_LABELS = Object.freeze({
  not_started: '未开始',
  in_progress: '进行中',
  ready_for_review: '待验收',
  completed: '已完成',
  blocked: '有卡点',
});

export class ProgressError extends Error {
  constructor(code, message) {
    super(`[${code}] ${message}`);
    this.code = code;
  }
}

/** 根路径 + 根相对 URL 拼接（days.json 内路径不带 base path）。 */
export function joinBasePath(basePath, url) {
  if (!url) return url;
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(url) || url.startsWith('#')) return url;
  const base = String(basePath || '').replace(/\/+$/, '');
  if (url.startsWith('/')) return (base + url) || url;
  return base ? `${base}/${url}` : url;
}

/** 返回某日课类型的适用任务（新数组，调用方不得修改共享常量）。 */
export function getApplicableTasks(dayType) {
  const tasks = TYPE_TASKS[dayType];
  if (!tasks) {
    throw new ProgressError('CONTENT_TYPE_UNSUPPORTED', `未知日课类型：${dayType}`);
  }
  return tasks.slice();
}

export function isKnownTask(taskId) {
  return TASK_IDS.includes(taskId);
}

export function isKnownStatus(status) {
  return TASK_STATUSES.has(status);
}

/** 按当前日课类型规范化任务表：适用任务缺省 not_started，不适用任务 not_applicable。 */
export function normalizeTasks(dayType, tasks, now) {
  const applicable = getApplicableTasks(dayType);
  const result = {};
  for (const taskId of TASK_IDS) {
    const existing = tasks && tasks[taskId];
    if (applicable.includes(taskId)) {
      const status = existing && isKnownStatus(existing.status) && existing.status !== 'not_applicable'
        ? existing.status
        : 'not_started';
      result[taskId] = { status, updated_at: (existing && existing.updated_at) || now };
    } else {
      result[taskId] = { status: 'not_applicable', updated_at: (existing && existing.updated_at) || now };
    }
  }
  return result;
}

/**
 * 四项子状态 → 整体状态（只读取适用任务）。
 * 优先级：blocked > completed > ready_for_review > in_progress > not_started。
 */
export function deriveDayState(dayType, tasks) {
  const applicable = getApplicableTasks(dayType);
  const statuses = applicable.map((taskId) => tasks[taskId] && tasks[taskId].status);
  if (statuses.some((s) => s === 'blocked')) return DAY_STATES.BLOCKED;
  if (statuses.every((s) => s === 'done')) return DAY_STATES.COMPLETED;
  const acceptanceIdx = applicable.indexOf('acceptance');
  if (acceptanceIdx !== -1) {
    const others = statuses.filter((_, i) => i !== acceptanceIdx);
    const acceptance = statuses[acceptanceIdx];
    if (others.every((s) => s === 'done') && (acceptance === 'not_started' || acceptance === 'in_progress')) {
      return DAY_STATES.READY_FOR_REVIEW;
    }
  }
  if (statuses.some((s) => s === 'in_progress' || s === 'done')) {
    return DAY_STATES.IN_PROGRESS;
  }
  return DAY_STATES.NOT_STARTED;
}

export function stateLabel(state) {
  return STATE_LABELS[state] || state;
}

export function taskLabel(taskId) {
  return TASK_LABELS[taskId] || taskId;
}

/** 新建日课记录：content_sha 直接确认为当前版本（doc 02 §2.4）。 */
export function createDayProgress(day, now) {
  return {
    schema_version: 1,
    day_id: day.day_id,
    content_sha: day.content_sha,
    planned: false,
    tasks: normalizeTasks(day.type, {}, now),
    latest_evidence_id: null,
    stuck_item_ids: [],
    last_visited_at: now,
    needs_review: false,
    revision: 0,
  };
}


/** 兼容普通对象与 Map 的记录查找。 */
function lookupRecord(recordsById, dayId) {
  if (!recordsById) return null;
  if (typeof recordsById.get === 'function') return recordsById.get(dayId) || null;
  return recordsById[dayId] || null;
}

function _lastTaskUpdate(record) {
  let latest = null;
  for (const taskId of TASK_IDS) {
    const task = record.tasks && record.tasks[taskId];
    if (task && task.updated_at && (!latest || task.updated_at > latest)) latest = task.updated_at;
  }
  return latest;
}

/** 标记某任务状态；不适用任务抛错；相同状态幂等返回原记录。 */
export function setTaskStatus(record, dayType, taskId, status, now) {
  if (!isKnownTask(taskId)) {
    throw new ProgressError('TASK_UNKNOWN', `未知任务：${taskId}`);
  }
  if (!isKnownStatus(status) || status === 'not_applicable') {
    throw new ProgressError('STATUS_INVALID', `非法任务状态：${status}`);
  }
  const applicable = getApplicableTasks(dayType);
  if (!applicable.includes(taskId)) {
    throw new ProgressError('TASK_NOT_APPLICABLE', `${dayType} 类型不包含任务 ${taskId}`);
  }
  const current = record.tasks[taskId];
  if (current.status === status) return record;
  return {
    ...record,
    tasks: { ...record.tasks, [taskId]: { status, updated_at: now } },
  };
}

export function setPlanned(record, planned, now) {
  if (record.planned === planned) return record;
  return { ...record, planned, last_visited_at: now };
}

/** 复核内容更新：只更新版本字段，不自动完成任务（doc 02 §2.4）。 */
export function acknowledgeContent(record, currentSha, now) {
  if (record.content_sha === currentSha && !record.needs_review) return record;
  return {
    ...record,
    content_sha: currentSha,
    needs_review: false,
    last_visited_at: now,
  };
}

export function touchVisited(record, now) {
  if (record.last_visited_at === now) return record;
  return { ...record, last_visited_at: now };
}

/** 内容版本变化：保留任务与引用，仅设置 needs_review。 */
export function markNeedsReview(record, currentSha) {
  if (record.needs_review || record.content_sha === currentSha) return record;
  return { ...record, needs_review: true };
}

function _dayActivity(record) {
  if (!record) return null;
  return {
    lastTaskUpdate: _lastTaskUpdate(record),
    lastVisited: record.last_visited_at || null,
  };
}

/** 汇总 168 天 / 周 / 阶段（doc 02 §2.6）。 */
export function summarizeDays(days, recordsById) {
  const dayStates = {};
  const counts = { completed: 0, in_progress: 0, blocked: 0, ready_for_review: 0, not_started: 0 };
  let needsReview = 0;
  let plannedAnomalies = [];

  const plannedRecords = [];
  for (const day of days) {
    const record = lookupRecord(recordsById, day.day_id);
    const state = record ? deriveDayState(day.type, record.tasks) : DAY_STATES.NOT_STARTED;
    dayStates[day.day_id] = state;
    counts[state] = (counts[state] || 0) + 1;
    if (record) {
      if (record.needs_review) needsReview += 1;
      if (record.planned) plannedRecords.push({ day, record });
    }
  }
  if (plannedRecords.length > 1) {
    plannedRecords.sort((a, b) => {
      const ua = _lastTaskUpdate(a.record) || a.record.last_visited_at || '';
      const ub = _lastTaskUpdate(b.record) || b.record.last_visited_at || '';
      return ub.localeCompare(ua);
    });
    plannedAnomalies = plannedRecords.slice(1).map((entry) => entry.day.day_id);
  }

  const weeks = [];
  const weeksByNumber = new Map();
  for (const day of days) {
    if (!weeksByNumber.has(day.week)) {
      weeksByNumber.set(day.week, []);
    }
    weeksByNumber.get(day.week).push(day);
  }
  for (const [week, weekDays] of [...weeksByNumber.entries()].sort((a, b) => a[0] - b[0])) {
    weeks.push(_summarizeWeek(week, weekDays, dayStates));
  }

  const phases = [];
  for (let phase = 1; phase <= 6; phase += 1) {
    const phaseWeeks = weeks.filter((w) => Math.floor((w.days[0].day - 1) / 28) + 1 === phase);
    const day28 = days.find((d) => d.phase === phase && d.day === phase * 28);
    phases.push(_summarizePhase(phase, phaseWeeks, day28, dayStates));
  }

  const totalDays = days.length;
  const completedDays = counts.completed;
  return {
    dayStates,
    counts,
    needsReview,
    plannedDayId: plannedRecords.length ? plannedRecords[0].day.day_id : null,
    plannedAnomalies,
    weeks,
    phases,
    totalDays,
    completedDays,
    completionPercent: totalDays ? Math.floor((completedDays / totalDays) * 100) : 0,
  };
}

function _inputState(day, dayStates) {
  return dayStates[day.day_id] || DAY_STATES.NOT_STARTED;
}

function _summarizeWeek(week, weekDays, dayStates) {
  const reviewDay = [...weekDays].reverse().find((d) => d.type === 'review');
  const keyDays = weekDays.filter((d) => d.key_output || d.type === 'integration' || d.type === 'review');
  const keyStates = keyDays.map((d) => _inputState(d, dayStates));
  const nonReviewKeyDays = keyDays.filter((d) => d !== reviewDay);
  let mainState;
  if (keyStates.some((s) => s === DAY_STATES.BLOCKED)) {
    mainState = DAY_STATES.BLOCKED;
  } else if (keyStates.length && keyStates.every((s) => s === DAY_STATES.COMPLETED)) {
    mainState = DAY_STATES.COMPLETED;
  } else if (
    nonReviewKeyDays.length &&
    nonReviewKeyDays.every((d) => _inputState(d, dayStates) === DAY_STATES.COMPLETED) &&
    reviewDay &&
    _inputState(reviewDay, dayStates) !== DAY_STATES.COMPLETED
  ) {
    mainState = DAY_STATES.READY_FOR_REVIEW;
  } else if (keyStates.some((s) => s !== DAY_STATES.NOT_STARTED)) {
    mainState = DAY_STATES.IN_PROGRESS;
  } else {
    mainState = DAY_STATES.NOT_STARTED;
  }
  const completed = weekDays.filter((d) => dayStates[d.day_id] === DAY_STATES.COMPLETED).length;
  return {
    week,
    phase: weekDays[0].phase,
    days: weekDays,
    mainState,
    keyDays,
    reviewDay,
    completedDays: completed,
    totalDays: weekDays.length,
    completionPercent: Math.floor((completed / weekDays.length) * 100),
  };
}

function _summarizePhase(phase, phaseWeeks, day28, dayStates) {
  const weekStates = phaseWeeks.map((w) => w.mainState);
  const day28State = day28 ? _inputState(day28, dayStates) : DAY_STATES.COMPLETED;
  let mainState;
  if (weekStates.some((s) => s === DAY_STATES.BLOCKED) || day28State === DAY_STATES.BLOCKED) {
    mainState = DAY_STATES.BLOCKED;
  } else if (weekStates.length && weekStates.every((s) => s === DAY_STATES.COMPLETED) && day28State === DAY_STATES.COMPLETED) {
    mainState = DAY_STATES.COMPLETED;
  } else if (weekStates.length && weekStates.every((s) => s === DAY_STATES.COMPLETED) && day28State !== DAY_STATES.COMPLETED) {
    mainState = DAY_STATES.READY_FOR_REVIEW;
  } else if (weekStates.some((s) => s !== DAY_STATES.NOT_STARTED) || day28State !== DAY_STATES.NOT_STARTED) {
    mainState = DAY_STATES.IN_PROGRESS;
  } else {
    mainState = DAY_STATES.NOT_STARTED;
  }
  const completed = phaseWeeks.reduce((sum, w) => sum + w.completedDays, 0);
  const total = phaseWeeks.reduce((sum, w) => sum + w.totalDays, 0);
  return {
    phase,
    weeks: phaseWeeks,
    day28,
    mainState,
    completedDays: completed,
    totalDays: total,
    completionPercent: total ? Math.floor((completed / total) * 100) : 0,
  };
}

/** 继续学习目标（doc 02 §2.5）。 */
export function getContinueTarget(days, recordsById) {
  if (!days.length) return null;
  const summary = summarizeDays(days, recordsById);

  // 1. 计划日（多条属数据异常：summarizeDays 已选最近更新的一条）
  if (summary.plannedDayId) {
    const day = days.find((d) => d.day_id === summary.plannedDayId);
    return { day, state: summary.dayStates[day.day_id], reason: 'planned', anomalies: summary.plannedAnomalies };
  }

  // 2. 进行中的周复盘优先（不被普通旧课浏览打断）
  let bestReview = null;
  for (const day of days) {
    if (day.type !== 'review') continue;
    const state = summary.dayStates[day.day_id];
    if (state !== DAY_STATES.IN_PROGRESS) continue;
    const activity = _dayActivity(lookupRecord(recordsById, day.day_id));
    if (!bestReview || (activity.lastTaskUpdate || '') > (bestReview.activity.lastTaskUpdate || '')) {
      bestReview = { day, state, activity };
    }
  }
  if (bestReview) return { day: bestReview.day, state: bestReview.state, reason: 'review' };

  // 3. 最近任务更新且未完成的日课（last_visited_at 平局）
  let best = null;
  for (const day of days) {
    const state = summary.dayStates[day.day_id];
    if (state === DAY_STATES.COMPLETED) continue;
    const record = lookupRecord(recordsById, day.day_id);
    if (!record) continue;
    const activity = _dayActivity(record);
    if (!activity.lastTaskUpdate && !activity.lastVisited) continue;
    if (
      !best ||
      (activity.lastTaskUpdate || '') > (best.activity.lastTaskUpdate || '') ||
      ((activity.lastTaskUpdate || '') === (best.activity.lastTaskUpdate || '') &&
        (activity.lastVisited || '') > (best.activity.lastVisited || ''))
    ) {
      best = { day, state, activity };
    }
  }
  if (best) return { day: best.day, state: best.state, reason: 'recent' };

  // 5. 全部完成
  if (summary.completedDays === summary.totalDays) {
    const last = days[days.length - 1];
    return { day: last, state: summary.dayStates[last.day_id], reason: 'done' };
  }

  // 4. 从未访问
  return { day: days[0], state: summary.dayStates[days[0].day_id], reason: 'first' };
}
