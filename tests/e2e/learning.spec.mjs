import { test, expect } from '@playwright/test';

/**
 * 进度闭环 E2E（对应 docs/development/05 §5.2）：
 * 任务勾选 → 事务保存 → 刷新恢复 → 计划当前日 → 首页继续学习。
 */

test('日课任务勾选后刷新仍保留', async ({ page }) => {
  await page.goto('tutorials/week-005/day-029/');
  const readingFieldset = page.locator('fieldset[data-task-id="reading"]');
  await expect(readingFieldset).toBeVisible();

  await readingFieldset.locator('input[value="done"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.reload();
  await expect(readingFieldset.locator('input[value="done"]')).toBeChecked();
  await expect(page.locator('[data-learning="day-state"]')).toContainText('进行中');
});

test('环境日不要求实验任务以外的项被误开放', async ({ page }) => {
  await page.goto('tutorials/week-001/day-007/');
  // 复盘日：experiment 不适用
  await expect(page.locator('fieldset[data-task-id="experiment"]')).toHaveCount(0);
  await expect(page.locator('.learning-task-na')).toContainText('实验');
});

test('设为当前计划后首页显示继续该日', async ({ page }) => {
  await page.goto('tutorials/week-005/day-029/');
  const planned = page.locator('[data-learning="planned-toggle"]');
  await planned.check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('/');
  const continueCard = page.locator('[data-learning="continue"]');
  await expect(continueCard).toBeVisible();
  await expect(continueCard).toContainText('Day 029', { timeout: 10000 });
});

test('浏览旧课不回退主计划', async ({ page }) => {
  await page.goto('tutorials/week-005/day-029/');
  await page.locator('[data-learning="planned-toggle"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('tutorials/week-001/day-001/');
  await page.locator('fieldset[data-task-id="reading"] input[value="in_progress"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('/');
  await expect(page.locator('[data-learning="continue"]')).toContainText('Day 029', { timeout: 10000 });
});
