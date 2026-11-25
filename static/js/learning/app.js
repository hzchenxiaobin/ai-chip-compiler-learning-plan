/**
 * app.js — 学习模块唯一组合入口（WP-04/WP-05/WP-06）。
 *
 * 对应 docs/development/02_前端学习模块.md §9 与 03_页面集成与交互.md：
 * - 读取 body data-* → 加载 days.json → openStore → 纯视图模型 → 渲染
 * - tutorial/home/week/phase/plan 增强；search 页初始化 search.js；settings 页数据管理
 * - 静态层永远可读；增强失败只影响对应组件，不清空静态内容
 * - 渲染只用 createElement/textContent，不用 innerHTML 处理不可信文本
 */

import {
  joinBasePath,
  deriveDayState,
  createDayProgress,
  setTaskStatus,
  setPlanned,
  acknowledgeContent,
  touchVisited,
  markNeedsReview,
  summarizeDays,
  getContinueTarget,
  stateLabel,
  taskLabel,
  getApplicableTasks,
  DAY_STATES,
} from './progress.js';
import {
  openStore,
  precheckImport,
  classifyImportEntries,
  applyImport,
  restorePreReplaceBackup,
  clearUiPrefs,
  StoreError,
} from './store.js';
import { createSearchController, tokenizeQuery } from './search.js';

const body = document.body;
const pageType = body.dataset.pageType || '';
const basePath = body.dataset.basePath || '';
const daysUrl = body.dataset.daysUrl || joinBasePath(basePath, 'learning/days.json');

function nowIso() {
  return new Date().toISOString();
}

function $(selector, root) {
  return (root || document).querySelector(selector);
}

function $$(selector, root) {
  return Array.from((root || document).querySelectorAll(selector));
}

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
  }
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

const STATE_ICONS = {
  not_started: '○',
  in_progress: '◐',
  ready_for_review: '◑',
  completed: '✓',
  blocked: '!',
};

function stateBadge(state) {
  return el('span', { class: `learning-state learning-state-${state}` }, `${STATE_ICONS[state] || '·'} ${stateLabel(state)}`);
}


/** replaceChildren 会把 null 字符串化；统一过滤空子节点。 */
function mountReplace(node, ...children) {
  const flattened = children.flat().filter((child) => child !== null && child !== undefined);
  node.replaceChildren(...flattened);
}

function setLiveText(node, text) {
  if (node) node.textContent = text;
}

// ---------------------------------------------------------------------------
// 启动
// ---------------------------------------------------------------------------

async function loadDays() {
  const response = await fetch(daysUrl, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`days.json 请求失败：${response.status}`);
  const data = await response.json();
  globalThis.__LEARNING_CONTENT_COMMIT__ = data.content_commit;
  return data.days;
}

async function main() {
  if (!pageType || pageType === 'phases') return;
  let days = null;
  try {
    days = await loadDays();
  } catch (err) {
    console.warn('[learning] days.json 加载失败，静态页面仍可浏览：', err.message);
    return;
  }
  if (pageType === 'search') {
    initSearchPage(days);
    return;
  }
  const store = await openStore();
  const offChange = store.onChange(() => renderCurrent(store, days));
  window.addEventListener('pagehide', () => {
    offChange && offChange();
    store.close && store.close();
  });
  await renderCurrent(store, days);
}

async function renderCurrent(store, days) {
  try {
    if (pageType === 'tutorial') await renderTutorialPage(store, days);
    else if (pageType === 'home') await renderHomePage(store, days);
    else if (pageType === 'week') await renderWeekPage(store, days);
    else if (pageType === 'phase') await renderPhasePage(store, days);
    else if (pageType === 'plan') await renderPlanPage(store, days);
    else if (pageType === 'settings') await renderSettingsPage(store, days);
  } catch (err) {
    console.warn('[learning] 页面增强失败：', err);
  }
}

// ---------------------------------------------------------------------------
// 日课页
// ---------------------------------------------------------------------------

async function renderTutorialPage(store, days) {
  const dayId = body.dataset.dayId;
  const contentSha = body.dataset.contentSha;
  const day = days.find((entry) => entry.day_id === dayId);
  if (!day) return;
  const mount = $('[data-learning="day-progress"]');
  if (!mount) return;

  let record = await store.getDay(dayId);
  let created = false;
  if (!record) {
    record = createDayProgress(day, nowIso());
    created = true;
  } else if (record.content_sha !== contentSha && !record.needs_review) {
    const marked = markNeedsReview(record, contentSha);
    if (marked !== record) {
      record = marked;
      created = true;
    }
  }

  // 同一会话同一日只写一次访问时间
  const visitKey = `learning.visited.${dayId}`;
  let touched = false;
  try {
    touched = sessionStorage.getItem(visitKey) === '1';
  } catch (err) {
    touched = false;
  }
  if (!touched) {
    const next = touchVisited(record, nowIso());
    try {
      sessionStorage.setItem(visitKey, '1');
    } catch (err) {
      /* 隐私模式忽略 */
    }
    await store.updateDay(dayId, () => next);
    record = (await store.getDay(dayId)) || next;
  }

  renderTutorialCard(store, day, record);
}

/**
 * 日课任务卡：监听器只绑定一次（mount.dataset.bound 守卫），
 * record 变化通过 syncCard 同步 radio/状态/提示，避免重复绑定。
 */
function renderTutorialCard(store, day, record) {
  const mount = $('[data-learning="day-progress"]');
  if (!mount) return;
  const saveState = $('[data-learning="save-state"]', mount);
  const plannedToggle = $('[data-learning="planned-toggle"]', mount);
  const ackButton = $('[data-learning="acknowledge-button"]', mount);

  function currentRecord() {
    return mount.__learningRecord || createDayProgress(day, nowIso());
  }

  function syncCard(dayRef, rec) {
    mount.__learningRecord = rec;
    const stateBox = $('[data-learning="day-state"]', mount);
    const reviewHint = $('[data-learning="review-hint"]', mount);
    const dayState = deriveDayState(dayRef.type, rec.tasks);
    if (stateBox) {
      mountReplace(stateBox, el('span', { class: 'learning-state-line' }, '整体状态：'), stateBadge(dayState));
    }
    if (reviewHint) reviewHint.hidden = !rec.needs_review;
    if (plannedToggle) plannedToggle.checked = !!rec.planned;
    const applicable = getApplicableTasks(dayRef.type);
    for (const fieldset of $$('fieldset.learning-task', mount)) {
      const taskId = fieldset.dataset.taskId;
      if (!applicable.includes(taskId)) continue;
      const status = (rec.tasks[taskId] || {}).status || 'not_started';
      for (const radio of $$('input[type="radio"]', fieldset)) radio.checked = radio.value === status;
    }
  }

  if (mount.dataset.bound !== '1') {
    mount.dataset.bound = '1';

    plannedToggle.addEventListener('change', () => {
      const current = currentRecord();
      const next = setPlanned(current, plannedToggle.checked, nowIso());
      void updateQuietly(store, day, next, plannedToggle, saveState, () => {
        syncCard(day, next);
      });
    });

    ackButton.addEventListener('click', () => {
      const next = acknowledgeContent(currentRecord(), body.dataset.contentSha, nowIso());
      void updateQuietly(store, day, next, ackButton, saveState, () => {
        syncCard(day, next);
      });
    });

    for (const fieldset of $$('fieldset.learning-task', mount)) {
      const taskId = fieldset.dataset.taskId;
      fieldset.addEventListener('change', (event) => {
        const target = event.target;
        if (target.type !== 'radio' || !target.checked) return;
        const recordNow = currentRecord();
        const previous = { ...(recordNow.tasks[taskId] || {}) };
        const radios = $$('input[type="radio"]', fieldset);
        for (const radio of radios) radio.disabled = true;
        let next;
        try {
          next = setTaskStatus(recordNow, day.type, taskId, target.value, nowIso());
        } catch (err) {
          setLiveText(saveState, `无法保存：${err.message}`);
          return;
        }
        store
          .updateDay(day.day_id, () => next)
          .then(() => {
            setLiveText(saveState, `已保存 ${new Date().toLocaleTimeString()}`);
            syncCard(day, next);
          })
          .catch((err) => {
            syncCard(day, recordWithTask(recordNow, taskId, previous));
            setLiveText(saveState, reportStoreError(err));
          })
          .finally(() => {
            for (const radio of radios) radio.disabled = false;
          });
      });
    }
  }

  syncCard(day, record);
}

function recordWithTask(record, taskId, previous) {
  return { ...record, tasks: { ...record.tasks, [taskId]: previous } };
}

async function updateQuietly(store, day, next, button, saveState, onDone) {
  const wasDisabled = button ? button.disabled : false;
  if (button) button.disabled = true;
  try {
    await store.updateDay(day.day_id, () => next);
    setLiveText(saveState, `已保存 ${new Date().toLocaleTimeString()}`);
    if (onDone) onDone();
  } catch (err) {
    setLiveText(saveState, reportStoreError(err));
  } finally {
    if (button) button.disabled = wasDisabled;
  }
}

function reportStoreError(err) {
  if (err instanceof StoreError) {
    if (err.code === 'STORAGE_QUOTA') return '本次更改未保存：存储配额不足，请导出备份后清理';
    return `本次更改未保存：${err.message}`;
  }
  return `本次更改未保存：${err && err.message ? err.message : '未知错误'}`;
}

// ---------------------------------------------------------------------------
// 首页 / 周页 / 阶段页 / 计划页
// ---------------------------------------------------------------------------

function storageNotice(store) {
  if (store.isPersistent) return null;
  return el('p', { class: 'learning-temp-note' }, '⚠ 当前浏览器存储不可用：进度仅本次会话有效，请及时在「我的数据」导出备份。');
}

async function renderHomePage(store, days) {
  const records = await store.getAllDays();
  const recordsById = new Map(records.map((record) => [record.day_id, record]));
  const summary = summarizeDays(days, recordsById);
  const target = getContinueTarget(days, recordsById);

  const continueMount = $('[data-learning="continue"]');
  if (continueMount) {
    const state = target ? target.state : DAY_STATES.NOT_STARTED;
    const buttonLabel =
      !target || target.reason === 'first'
        ? `开始第 ${target.day.day} 天`
        : target.reason === 'done'
          ? '查看完整学习计划'
          : state === DAY_STATES.BLOCKED
            ? `查看第 ${target.day.day} 天卡点`
            : state === DAY_STATES.READY_FOR_REVIEW
              ? `完成第 ${target.day.day} 天验收`
              : target.reason === 'planned' || target.reason === 'recent' || target.reason === 'review'
                ? `继续第 ${target.day.day} 天`
                : `开始第 ${target.day.day} 天`;
    const href = target.reason === 'done' ? joinBasePath(basePath, 'plan.html') : joinBasePath(basePath, target.day.url);
    mountReplace(continueMount, 
      el('h3', { text: '继续学习' }),
      storageNotice(store),
      el(
        'a',
        { class: 'learning-continue-main', href },
        el('span', { class: 'learning-continue-day', text: `Day ${String(target.day.day).padStart(3, '0')}` }),
        el('span', { class: 'learning-continue-title', text: target.day.title }),
        stateBadge(state),
        el('span', { class: 'learning-continue-cta', text: `${buttonLabel} →` })
      ),
      summary.plannedAnomalies.length
        ? el('p', { class: 'learning-anomaly-note' }, `检测到 ${summary.plannedAnomalies.length + 1} 条“当前计划”记录（数据异常），已选择最近更新的一条；可在设置页检查。`)
        : null
    );
  }

  const overviewMount = $('[data-learning="overview"]');
  if (overviewMount) {
    mountReplace(overviewMount, 
      el('h3', { text: '学习概览' }),
      storageNotice(store),
      el('ul', { class: 'learning-overview-list' },
        el('li', {}, `已完成 ${summary.counts.completed || 0} 天 · 进行中 ${summary.counts.in_progress || 0} 天 · 卡点 ${summary.counts.blocked || 0} 天`),
        el('li', {}, `待复核 ${summary.needsReview} 天 · 辅助完成率 ${summary.completedDays}/${summary.totalDays}（${summary.completionPercent}%）`),
        el('li', {}, '进度保存在本浏览器；换设备请先导出备份。')
      )
    );
  }

  const quickForm = $('[data-learning="quick-search"]');
  if (quickForm && !quickForm.dataset.enhanced) {
    quickForm.dataset.enhanced = '1';
    quickForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const input = $('input[name="q"]', quickForm);
      const query = (input && input.value ? input.value : '').trim();
      const url = new URL(joinBasePath(basePath, 'search/'), window.location.href);
      if (query) url.searchParams.set('q', query);
      window.location.href = url.href;
    });
  }
}

function weekPhaseSummaryContent(store, summaryLine, mainState, auxDone, auxTotal, extraNodes) {
  return [
    storageNotice(store),
    el('p', { class: 'learning-main-state' }, '主状态：'), stateBadge(mainState), el('span', { class: 'learning-main-hint', text: summaryLine }),
    el('p', { class: 'learning-aux-progress' },
      el('progress', { value: String(auxDone), max: String(auxTotal) }),
      `已完成 ${auxDone}/${auxTotal} 天（辅助指标）`
    ),
    ...(extraNodes || []),
  ];
}

async function renderWeekPage(store, days) {
  const mount = $('[data-learning="week-progress"]');
  if (!mount) return;
  const week = Number(body.dataset.week);
  const records = await store.getAllDays();
  const recordsById = new Map(records.map((record) => [record.day_id, record]));
  const summary = summarizeDays(days, recordsById);
  const weekSummary = summary.weeks.find((entry) => entry.week === week);
  if (!weekSummary) return;
  const stateCounts = { completed: 0, in_progress: 0, blocked: 0, ready_for_review: 0 };
  for (const day of weekSummary.days) {
    const state = summary.dayStates[day.day_id];
    if (stateCounts[state] !== undefined) stateCounts[state] += 1;
  }
  const reviewState = weekSummary.reviewDay ? summary.dayStates[weekSummary.reviewDay.day_id] : null;
  mountReplace(mount, 
    el('h2', { text: '本周进度' }),
    ...weekPhaseSummaryContent(
      store,
      '周主状态由关键产出、Day 6 集成与 Day 7 复盘派生，不以阅读百分比代替。',
      weekSummary.mainState,
      weekSummary.completedDays,
      weekSummary.totalDays,
      [
        el('p', { class: 'learning-week-counts' },
          `已完成 ${stateCounts.completed} · 进行中 ${stateCounts.in_progress} · 待验收 ${stateCounts.ready_for_review} · 卡点 ${stateCounts.blocked}`),
        reviewState ? el('p', { class: 'learning-week-review' }, `Day 7 复盘：`) : null,
        reviewState ? stateBadge(reviewState) : null,
      ]
    )
  );
}

async function renderPhasePage(store, days) {
  const mount = $('[data-learning="phase-progress"]');
  if (!mount) return;
  const phase = Number(body.dataset.phase);
  const records = await store.getAllDays();
  const recordsById = new Map(records.map((record) => [record.day_id, record]));
  const summary = summarizeDays(days, recordsById);
  const phaseSummary = summary.phases.find((entry) => entry.phase === phase);
  if (!phaseSummary) return;
  const weekNodes = phaseSummary.weeks.map((week) =>
    el('li', { class: 'learning-phase-week' }, `第 ${week.week} 周：`, stateBadge(week.mainState), `（关键产出完成 ${week.completedDays}/${week.totalDays}）`)
  );
  mountReplace(mount, 
    el('h2', { text: '阶段进度' }),
    ...weekPhaseSummaryContent(
      store,
      '阶段主状态由四周关键产出与第 28 天综合复盘派生。',
      phaseSummary.mainState,
      phaseSummary.completedDays,
      phaseSummary.totalDays,
      [el('ul', { class: 'learning-phase-weeks' }, ...weekNodes)]
    )
  );
}

async function renderPlanPage(store, days) {
  const records = await store.getAllDays();
  const recordsById = new Map(records.map((record) => [record.day_id, record]));
  const summary = summarizeDays(days, recordsById);
  for (const pill of $$('.vp-nav-pills a[data-day-id]')) {
    const state = summary.dayStates[pill.dataset.dayId];
    if (!state) continue;
    pill.classList.add(`learning-pill-${state}`);
    pill.title = `${pill.title}（${stateLabel(state)}）`;
  }
}

// ---------------------------------------------------------------------------
// 搜索页
// ---------------------------------------------------------------------------

function initSearchPage(days) {
  const form = $('[data-learning="search-form"]');
  const resultsMount = $('[data-learning="search-results"]');
  const liteStatus = $('[data-learning="lite-status"]');
  const phaseStatus = $('[data-learning="phase-status"]');
  if (!form || !resultsMount) return;
  const controller = createSearchController({ daysUrl, basePath });
  const input = $('#learning-search-q', form);
  const scopeSelect = $('[data-learning="scope-select"]', form);
  const phaseSelect = $('[data-learning="phase-select"]', form);
  const weekSelect = $('[data-learning="week-select"]', form);
  const typeSelect = $('[data-learning="type-select"]', form);
  let debounceTimer = null;
  const RESULT_STEP = 50;
  let visibleCount = RESULT_STEP;

  function currentFilters() {
    return {
      phase: phaseSelect && phaseSelect.value ? phaseSelect.value : null,
      week: weekSelect && weekSelect.value ? weekSelect.value : null,
      type: typeSelect && typeSelect.value ? typeSelect.value : null,
    };
  }

  function syncUrl(query, scope) {
    try {
      const url = new URL(window.location.href);
      if (query) url.searchParams.set('q', query);
      else url.searchParams.delete('q');
      if (scope === 'full') url.searchParams.set('scope', 'full');
      else url.searchParams.delete('scope');
      window.history.replaceState(null, '', url);
    } catch (err) {
      /* ignore */
    }
  }

  function renderResults(response) {
    visibleCount = RESULT_STEP;
    const items = response.results.slice(0, visibleCount);
    const nodes = [];
    if (!response.query.trim()) {
      nodes.push(el('p', { class: 'learning-search-hint' }, '输入关键词开始搜索；支持中文、命令、错误码与文件名。'));
    } else if (!items.length) {
      nodes.push(
        el('div', { class: 'learning-search-empty' },
          el('p', {}, `没有找到与「${response.query}」相关的${response.scope === 'full' ? '正文' : '课程'}结果。`),
          el('p', {}, '建议：缩短关键词、尝试命令/错误码完整文本（如 mlir-opt）、或切换到全文范围。')
        )
      );
    } else {
      for (const item of items) {
        nodes.push(
          el('a', { class: 'learning-search-item', href: item.url },
            el('span', { class: 'learning-search-day', text: `Day ${String(item.day).padStart(3, '0')}` }),
            el('span', { class: 'learning-search-title', text: item.title }),
            item.heading ? el('span', { class: 'learning-search-heading', text: `§ ${item.heading}` }) : null,
            el('span', { class: 'learning-search-snippet', text: item.snippet }),
            el('span', { class: 'learning-search-meta', text: (item.matchedFields || []).join('·') })
          )
        );
      }
      if (response.results.length > visibleCount) {
        nodes.push(
          el('button', {
            class: 'learning-button',
            type: 'button',
            onclick: () => {
              visibleCount += RESULT_STEP;
              renderResults(response);
            },
          }, `显示更多（共 ${response.results.length} 条）`)
        );
      }
    }
    mountReplace(resultsMount, nodes);
  }

  function runLite(query) {
    controller
      .searchLite(query, currentFilters())
      .then((response) => {
        setLiveText(liteStatus, response.query ? `课程信息：${response.results.length} 条结果` : '');
        renderResults(response);
      })
      .catch((err) => {
        setLiveText(liteStatus, `课程信息搜索失败：${err.message}（可重试）`);
      });
  }

  function runFull(query) {
    setLiveText(phaseStatus, '正在加载正文分片…');
    controller
      .searchFull(query, currentFilters())
      .then((response) => {
        setLiveText(phaseStatus, `全文（阶段 ${(response.loadedPhases || []).join('、') || '—'}）：${response.results.length} 条结果`);
        renderResults(response);
      })
      .catch((err) => {
        setLiveText(phaseStatus, `正文搜索失败：${err.message}；已成功的轻量结果保留（正文结果不完整）。可点击“搜索”重试。`);
      });
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const query = (input && input.value ? input.value : '').trim();
    const scope = scopeSelect && scopeSelect.value === 'full' ? 'full' : 'lite';
    syncUrl(query, scope);
    if (scope === 'full') runFull(query);
    else runLite(query);
  });

  if (input) {
    input.addEventListener('input', () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const query = input.value.trim();
        syncUrl(query, 'lite');
        runLite(query);
      }, 150);
    });
  }

  window.addEventListener('pagehide', () => controller.cancel());

  const initial = new URL(window.location.href).searchParams;
  const initialQuery = (initial.get('q') || '').trim();
  if (input && initialQuery) input.value = initialQuery;
  if (initial.get('scope') === 'full' && scopeSelect) scopeSelect.value = 'full';
  if (initialQuery && initial.get('scope') === 'full') runFull(initialQuery);
  else if (initialQuery) runLite(initialQuery);
}

// ---------------------------------------------------------------------------
// 设置页
// ---------------------------------------------------------------------------

async function renderSettingsPage(store, days) {
  renderStorageStatus(store);
  wireExport(store, days);
  wireImport(store, days);
  wireClear(store);
}

async function renderStorageStatus(store) {
  const mount = $('[data-learning="storage-status"]');
  if (!mount) return;
  const render = async () => {
    let content;
    if (store.isPersistent) {
      const records = await store.getAllDays();
      let latest = '';
      for (const record of records) {
        if (record.last_visited_at && record.last_visited_at > latest) latest = record.last_visited_at;
      }
      content = [
        el('p', { class: 'learning-storage-ok' }, '✓ 进度保存在此浏览器（IndexedDB），不会自动上传。'),
        el('p', {}, `已有记录：${records.length} 天${latest ? `；最近更新 ${new Date(latest).toLocaleString()}` : ''}`),
      ];
    } else {
      content = [
        el('p', { class: 'learning-temp-note' }, '⚠ 浏览器存储不可用：进度仅保存在当前页面会话的内存中，刷新后会丢失。'),
        el('p', {}, '课程阅读、搜索与源码下载不受影响；建议尽快导出备份。导出不承诺一定成功，以实际结果为准。'),
      ];
    }
    mountReplace(mount, el('h2', { text: '存储状态' }), ...content);
  };
  await render();
  store.onChange(render);
}

function wireExport(store, days) {
  const button = $('[data-learning="export-button"]');
  const result = $('[data-learning="export-result"]');
  if (!button || !result) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const blob = await store.exportProgress(days);
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const filename = `ai-chip-compiler-learning-backup-${stamp}.json`;
      const url = URL.createObjectURL(blob);
      const link = el('a', { href: url, download: filename });
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
      setLiveText(result, `已导出 ${filename}`);
    } catch (err) {
      setLiveText(result, `导出失败：${err.message}`);
    } finally {
      button.disabled = false;
    }
  });
}

function wireImport(store, days) {
  const form = $('[data-learning="import-form"]');
  const fileInput = $('[data-learning="import-file"]');
  const preview = $('[data-learning="import-preview"]');
  const conflictsBox = $('[data-learning="import-conflicts"]');
  const result = $('[data-learning="import-result"]');
  if (!form || !fileInput || !preview) return;
  let currentPlan = null;
  let resolutions = {};

  const resetUi = () => {
    currentPlan = null;
    resolutions = {};
    preview.replaceChildren();
    if (conflictsBox) mountReplace(conflictsBox, );
  };

  fileInput.addEventListener('change', resetUi);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      setLiveText(result, '请先选择 JSON 备份文件。');
      return;
    }
    const mode = ($('input[name="import-mode"]:checked', form) || {}).value === 'replace' ? 'replace' : 'merge';
    setLiveText(result, '正在预检…');
    try {
      if (!currentPlan) {
        const plan = await precheckImport(file, days);
        currentPlan = await classifyImportEntries(store, plan);
        renderPreview();
      }
      if (!currentPlan) return;
      const pending = currentPlan.summary.conflict;
      if (pending > 0 && Object.keys(resolutions).length < pending) {
        setLiveText(result, `还有 ${pending} 条冲突未选择（保留本机 / 使用导入 / 稍后处理），完成选择后再导入。`);
        return;
      }
      if (mode === 'replace' && !form.dataset.replaceConfirmed) {
        form.dataset.replaceConfirmed = '1';
        setLiveText(result, '替换模式将清空当前全部进度并用导入内容覆盖（会先自动备份）。再次点击“预检并导入”确认执行。');
        return;
      }
      delete form.dataset.replaceConfirmed;
      const report = await applyImport(store, currentPlan, { mode, resolutions });
      if (report.failed) {
        setLiveText(result, `导入失败（数据库未变化）：${report.error && report.error.message ? report.error.message : '未知错误'}`);
      } else {
        setLiveText(
          result,
          `导入完成（${mode === 'replace' ? '替换' : '合并'}）：写入 ${report.added} 条，跳过 ${report.skipped}，未变化 ${report.unchanged}，未处理冲突 ${report.conflictsPending}。`
        );
        resetUi();
        fileInput.value = '';
        renderStorageStatus(store);
      }
    } catch (err) {
      setLiveText(result, err instanceof StoreError ? err.message : `导入失败：${err.message}`);
    }
  });

  function renderPreview() {
    const plan = currentPlan;
    const summary = plan.summary;
    const nodes = [
      el('p', {}, `文件包含 ${plan.rawCount} 条记录：新增 ${summary.new} · 更新 ${summary.update} · 跳过（本机更新） ${summary.skip} · 未变化 ${summary.unchanged} · 冲突 ${summary.conflict} · 未知日课 ${summary.unknown_day}`),
    ];
    if (plan.unknownFieldsCount) {
      nodes.push(el('p', { class: 'learning-res-note' }, `忽略 ${plan.unknownFieldsCount} 个扩展字段（白名单外字段不进入数据库）。`));
    }
    if (plan.unknownDays.length) {
      nodes.push(el('p', { class: 'learning-res-note' }, `将跳过 ${plan.unknownDays.length} 条其他课程版本的记录：${plan.unknownDays.slice(0, 5).join('、')}${plan.unknownDays.length > 5 ? '…' : ''}`));
    }
    mountReplace(preview, nodes);

    if (conflictsBox && summary.conflict > 0) {
      const items = plan.entries
        .filter((entry) => entry.action === 'conflict')
        .map((entry) => {
          const group = el('fieldset', { class: 'learning-conflict', 'data-day': entry.dayId }, el('legend', { text: entry.dayId }));
          for (const [value, label] of [['local', '保留本机'], ['incoming', '使用导入'], ['later', '稍后手动处理']]) {
            const radio = el('input', { type: 'radio', name: `conflict-${entry.dayId}`, value });
            radio.addEventListener('change', () => {
              if (radio.checked) {
                resolutions[entry.dayId] = value;
                setLiveText(result, `已选择 ${entry.dayId}：${label}。`);
              }
            });
            group.append(el('label', { class: 'learning-task-option' }, radio, ` ${label}`));
          }
          return group;
        });
      mountReplace(conflictsBox, el('h3', { text: '冲突记录（同 revision 但内容不同）' }), ...items);
    }
  }

  const restoreButton = $('[data-learning="restore-backup"]');
  if (restoreButton) {
    restoreButton.addEventListener('click', async () => {
      try {
        const count = await restorePreReplaceBackup(store);
        setLiveText(result, `已从替换前备份恢复 ${count} 条记录。`);
        renderStorageStatus(store);
      } catch (err) {
        setLiveText(result, err instanceof StoreError ? err.message : `恢复失败：${err.message}`);
      }
    });
  }
}

function wireClear(store) {
  const result = $('[data-learning="clear-result"]');
  const clearProgressButton = $('[data-learning="clear-progress"]');
  if (clearProgressButton) {
    clearProgressButton.addEventListener('click', async () => {
      if (clearProgressButton.dataset.armed !== '1') {
        clearProgressButton.dataset.armed = '1';
        clearProgressButton.textContent = '确认清空？（不可撤销，建议先导出）';
        setTimeout(() => {
          clearProgressButton.dataset.armed = '';
          clearProgressButton.textContent = '清空学习记录…';
        }, 6000);
        return;
      }
      clearProgressButton.dataset.armed = '';
      clearProgressButton.textContent = '清空学习记录…';
      try {
        await store.clearProgress();
        const remaining = await store.getAllDays();
        if (remaining.length === 0) {
          setLiveText(result, '学习记录已清空（已验证计数为 0）；主题与 UI 偏好未修改。');
        } else {
          setLiveText(result, `清空异常：仍有 ${remaining.length} 条记录。`);
        }
        renderStorageStatus(store);
      } catch (err) {
        setLiveText(result, `清空失败：${err.message}`);
      }
    });
  }

  const clearPrefsButton = $('[data-learning="clear-prefs"]');
  if (clearPrefsButton) {
    clearPrefsButton.addEventListener('click', () => {
      const cleared = clearUiPrefs();
      setLiveText(result, `已清除本地偏好键：${cleared.join('、') || '无'}；学习记录不受影响。`);
    });
  }
}

// ---------------------------------------------------------------------------

main().catch((err) => console.warn('[learning] 初始化失败：', err));



