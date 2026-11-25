/**
 * tests/unit/test_progress.mjs — progress.js 纯状态机测试（WP-04）。
 * 运行：node --test tests/unit/
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  TASK_IDS,
  DAY_STATES,
  getApplicableTasks,
  normalizeTasks,
  deriveDayState,
  createDayProgress,
  setTaskStatus,
  setPlanned,
  acknowledgeContent,
  touchVisited,
  markNeedsReview,
  summarizeDays,
  getContinueTarget,
  joinBasePath,
} from '../../static/js/learning/progress.js';

const NOW = '2026-11-24T09:00:00.000Z';

function dayFixture(day, type, extra = {}) {
  return {
    day_id: `day-${String(day).padStart(3, '0')}`,
    day,
    week: Math.floor((day - 1) / 7) + 1,
    phase: Math.floor((day - 1) / 28) + 1,
    type,
    key_output: extra.key_output !== undefined ? extra.key_output : ['integration', 'review', 'final_assessment'].includes(type),
    title: `Day ${day}`,
    url: `tutorials/week-${String(Math.floor((day - 1) / 7) + 1).padStart(3, '0')}/day-${String(day).padStart(3, '0')}/`,
    content_sha: 'a'.repeat(64),
    ...extra,
  };
}

function recordWith(day, statuses, extra = {}) {
  const record = createDayProgress(day, NOW);
  for (const [taskId, status] of Object.entries(statuses)) {
    record.tasks[taskId] = { status, updated_at: NOW };
  }
  return { ...record, ...extra };
}

test('TASK_IDS 与七种类型的适用任务', () => {
  assert.deepEqual([...TASK_IDS], ['reading', 'exercise', 'experiment', 'acceptance']);
  assert.deepEqual(getApplicableTasks('review'), ['reading', 'exercise', 'acceptance']);
  assert.deepEqual(getApplicableTasks('documentation'), ['reading', 'exercise', 'acceptance']);
  assert.deepEqual(getApplicableTasks('presentation'), ['reading', 'exercise', 'acceptance']);
  assert.deepEqual(getApplicableTasks('concept_lab'), [...TASK_IDS]);
  assert.deepEqual(getApplicableTasks('environment_lab'), [...TASK_IDS]);
  assert.deepEqual(getApplicableTasks('integration'), [...TASK_IDS]);
  assert.deepEqual(getApplicableTasks('final_assessment'), [...TASK_IDS]);
  assert.throws(() => getApplicableTasks('unknown_type'), /CONTENT_TYPE_UNSUPPORTED/);
  // 返回新数组，修改不影响后续调用
  const arr = getApplicableTasks('review');
  arr.push('hacked');
  assert.equal(getApplicableTasks('review').length, 3);
});

test('deriveDayState：blocked 优先级最高', () => {
  const state = deriveDayState('concept_lab', {
    reading: { status: 'done', updated_at: NOW },
    exercise: { status: 'done', updated_at: NOW },
    experiment: { status: 'blocked', updated_at: NOW },
    acceptance: { status: 'in_progress', updated_at: NOW },
  });
  assert.equal(state, DAY_STATES.BLOCKED);
});

test('deriveDayState：全部适用任务 done → completed', () => {
  const tasks = {};
  for (const taskId of getApplicableTasks('review')) tasks[taskId] = { status: 'done', updated_at: NOW };
  assert.equal(deriveDayState('review', tasks), DAY_STATES.COMPLETED);
});

test('deriveDayState：验收未开始/进行中且其余完成 → ready_for_review', () => {
  for (const acceptance of ['not_started', 'in_progress']) {
    const state = deriveDayState('concept_lab', {
      reading: { status: 'done', updated_at: NOW },
      exercise: { status: 'done', updated_at: NOW },
      experiment: { status: 'done', updated_at: NOW },
      acceptance: { status: acceptance, updated_at: NOW },
    });
    assert.equal(state, DAY_STATES.READY_FOR_REVIEW, `acceptance=${acceptance}`);
  }
});

test('deriveDayState：验收 done 但练习未完成 → in_progress（不能是 completed）', () => {
  const state = deriveDayState('concept_lab', {
    reading: { status: 'done', updated_at: NOW },
    exercise: { status: 'in_progress', updated_at: NOW },
    experiment: { status: 'done', updated_at: NOW },
    acceptance: { status: 'done', updated_at: NOW },
  });
  assert.equal(state, DAY_STATES.IN_PROGRESS);
});

test('deriveDayState：复盘日不要求 experiment，全部适用项完成才算 completed', () => {
  const tasks = normalizeTasks('review', {}, NOW);
  assert.equal(tasks.experiment.status, 'not_applicable');
  assert.equal(deriveDayState('review', tasks), DAY_STATES.NOT_STARTED);
  tasks.reading = { status: 'done', updated_at: NOW };
  tasks.exercise = { status: 'done', updated_at: NOW };
  tasks.acceptance = { status: 'not_started', updated_at: NOW };
  assert.equal(deriveDayState('review', tasks), DAY_STATES.READY_FOR_REVIEW);
  tasks.acceptance = { status: 'done', updated_at: NOW };
  assert.equal(deriveDayState('review', tasks), DAY_STATES.COMPLETED);
});

test('setTaskStatus：不适用任务抛错；相同状态幂等', () => {
  const record = recordWith(dayFixture(1, 'review'), {});
  assert.throws(() => setTaskStatus(record, 'review', 'experiment', 'done', NOW), /TASK_NOT_APPLICABLE/);
  const same = setTaskStatus(record, 'review', 'reading', 'not_started', NOW);
  assert.equal(same, record);
  const changed = setTaskStatus(record, 'review', 'reading', 'done', NOW);
  assert.notEqual(changed, record);
  assert.equal(changed.tasks.reading.status, 'done');
  assert.equal(changed.tasks.reading.updated_at, NOW);
  // 原记录不被修改
  assert.equal(record.tasks.reading.status, 'not_started');
});

test('内容版本复核：SHA 变化保留任务，复核只更新版本字段', () => {
  const day = dayFixture(1, 'concept_lab', { content_sha: 'a'.repeat(64) });
  const record = recordWith(day, { reading: 'done', exercise: 'in_progress' }, { planned: true, revision: 5 });
  const newSha = 'b'.repeat(64);
  const marked = markNeedsReview(record, newSha);
  assert.equal(marked.needs_review, true);
  assert.equal(marked.tasks.reading.status, 'done');
  assert.equal(marked.planned, true);
  const acknowledged = acknowledgeContent(record, newSha, NOW);
  assert.equal(acknowledged.content_sha, newSha);
  assert.equal(acknowledged.needs_review, false);
  assert.equal(acknowledged.tasks.exercise.status, 'in_progress');
  assert.equal(acknowledged.planned, true);
});

test('planned 与浏览分离：touchVisited 不改 planned', () => {
  const day = dayFixture(3, 'concept_lab');
  const record = recordWith(day, {});
  const visited = touchVisited(record, '2026-11-25T10:00:00.000Z');
  assert.equal(visited.planned, false);
  assert.equal(visited.last_visited_at, '2026-11-25T10:00:00.000Z');
  const planned = setPlanned(visited, true, NOW);
  assert.equal(planned.planned, true);
});

test('normalizeTasks：导入的 not_applicable 按当前类型重新规范化', () => {
  const tasks = normalizeTasks('concept_lab', { experiment: { status: 'not_applicable', updated_at: NOW } }, NOW);
  assert.equal(tasks.experiment.status, 'not_started');
  const tasks2 = normalizeTasks('review', { experiment: { status: 'done', updated_at: NOW } }, NOW);
  assert.equal(tasks2.experiment.status, 'not_applicable');
});

test('summarizeDays：周主状态由关键产出派生，7/7 阅读不算完成', () => {
  const days = [];
  for (let d = 1; d <= 7; d += 1) {
    const type = d === 6 ? 'integration' : d === 7 ? 'review' : 'concept_lab';
    days.push(dayFixture(d, type));
  }
  const recordsById = {};
  // 前 5 天全部完成（阅读+练习+实验），第 6 天完成，第 7 天未动
  for (let d = 1; d <= 6; d += 1) {
    const statuses = d === 6
      ? { reading: 'done', exercise: 'done', experiment: 'done', acceptance: 'done' }
      : { reading: 'done', exercise: 'done', experiment: 'done', acceptance: 'done' };
    recordsById[days[d - 1].day_id] = recordWith(days[d - 1], statuses);
  }
  const summary = summarizeDays(days, recordsById);
  const week = summary.weeks[0];
  assert.equal(week.mainState, DAY_STATES.READY_FOR_REVIEW);
  assert.equal(summary.counts.completed, 6);
  // 反例：只有阅读 7 天全 done、关键产出未动 → 周 not_started/in_progress，不显示已掌握
  const liteRecords = {};
  for (let d = 1; d <= 7; d += 1) {
    const applicable = getApplicableTasks(days[d - 1].type);
    const tasks = {};
    for (const taskId of applicable) tasks[taskId] = { status: 'not_started', updated_at: NOW };
    tasks.reading = { status: 'done', updated_at: NOW };
    liteRecords[days[d - 1].day_id] = { ...createDayProgress(days[d - 1], NOW), tasks };
  }
  const summary2 = summarizeDays(days, liteRecords);
  assert.notEqual(summary2.weeks[0].mainState, DAY_STATES.COMPLETED);
  assert.notEqual(summary2.weeks[0].mainState, DAY_STATES.READY_FOR_REVIEW);
});

test('summarizeDays：任一关键项 blocked → 周 blocked', () => {
  const days = [1, 2, 6, 7].map((d) => dayFixture(d, d === 6 ? 'integration' : d === 7 ? 'review' : 'concept_lab'));
  const recordsById = {};
  recordsById['day-006'] = recordWith(days[2], { reading: 'blocked', exercise: 'not_started', experiment: 'not_started', acceptance: 'not_started' });
  const summary = summarizeDays(days, recordsById);
  assert.equal(summary.weeks[0].mainState, DAY_STATES.BLOCKED);
});

test('getContinueTarget：planned 优先，浏览旧课不回退', () => {
  const days = [dayFixture(1, 'concept_lab'), dayFixture(2, 'concept_lab'), dayFixture(3, 'concept_lab')];
  const recordsById = {
    'day-003': recordWith(days[2], { reading: 'done' }, { planned: true, last_visited_at: '2026-11-20T09:00:00.000Z' }),
    'day-001': recordWith(days[0], { reading: 'in_progress' }, { last_visited_at: '2026-11-24T09:00:00.000Z' }),
  };
  const target = getContinueTarget(days, recordsById);
  assert.equal(target.day.day_id, 'day-003');
  assert.equal(target.reason, 'planned');
});

test('getContinueTarget：无计划时选最近更新未完成；从未访问回 day-001；全部完成回最后一天', () => {
  const days = [dayFixture(1, 'concept_lab'), dayFixture(2, 'concept_lab')];
  assert.equal(getContinueTarget(days, {}).reason, 'first');
  const recordsById = {
    'day-001': recordWith(days[0], { reading: 'in_progress' }, { last_visited_at: '2026-11-23T09:00:00.000Z' }),
    'day-002': recordWith(days[1], { reading: 'done', exercise: 'done', experiment: 'done', acceptance: 'in_progress' }, { last_visited_at: '2026-11-22T09:00:00.000Z' }),
  };
  recordsById['day-001'].tasks.reading.updated_at = '2026-11-24T08:00:00.000Z';
  recordsById['day-002'].tasks.acceptance.updated_at = '2026-11-24T07:00:00.000Z';
  const target = getContinueTarget(days, recordsById);
  assert.equal(target.day.day_id, 'day-001');
  const done = {
    'day-001': recordWith(days[0], { reading: 'done', exercise: 'done', experiment: 'done', acceptance: 'done' }),
    'day-002': recordWith(days[1], { reading: 'done', exercise: 'done', experiment: 'done', acceptance: 'done' }),
  };
  assert.equal(getContinueTarget(days, done).reason, 'done');
});

test('joinBasePath：根相对路径与 base path 拼接', () => {
  assert.equal(joinBasePath('', 'tutorials/week-001/day-001/'), 'tutorials/week-001/day-001/');
  assert.equal(joinBasePath('/ai-chip-compiler-learning-plan', 'tutorials/week-001/day-001/'), '/ai-chip-compiler-learning-plan/tutorials/week-001/day-001/');
  assert.equal(joinBasePath('/x/', 'learning/days.json'), '/x/learning/days.json');
  assert.equal(joinBasePath('', 'https://github.com/x'), 'https://github.com/x');
  assert.equal(joinBasePath('/x', '#anchor'), '#anchor');
});
