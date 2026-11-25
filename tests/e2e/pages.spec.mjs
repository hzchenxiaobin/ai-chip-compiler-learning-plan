import { test, expect } from '@playwright/test';

/**
 * 周页/阶段页增强（docs/development/03 §4—5）：
 * 逐日状态徽标随本地记录变化；“继续本周”指向正确的未完成日。
 */

test('周页逐日状态标记与继续本周链接', async ({ page }) => {
  await page.goto('tutorials/week-005/day-029/');
  await page.locator('fieldset[data-task-id="reading"] input[value="done"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('weeks/week-005/');
  const day029Row = page.locator('.learning-day-row[data-day-id="day-029"]');
  await expect(day029Row.locator('[data-learning="day-state-mark"]')).toContainText('进行中', { timeout: 10000 });

  const continueLink = page.locator('[data-learning="continue-week"]');
  await expect(continueLink).toBeVisible();
  await expect(continueLink).toContainText('Day 29');
  const href = await continueLink.getAttribute('href');
  expect(href).toContain('tutorials/week-005/day-029/');

  // 未开始的日课不显示状态徽标
  await expect(page.locator('.learning-day-row[data-day-id="day-030"] [data-learning="day-state-mark"]')).toBeHidden();
});

test('阶段页逐日状态与继续本阶段', async ({ page }) => {
  await page.goto('tutorials/week-009/day-058/');
  await page.locator('fieldset[data-task-id="reading"] input[value="in_progress"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('phases/phase-3/');
  await expect(page.locator('.learning-day-row[data-day-id="day-058"] [data-learning="day-state-mark"]')).toContainText('进行中', { timeout: 10000 });
  await expect(page.locator('[data-learning="continue-phase"]')).toContainText('Day 58');
});

test('搜索结果高亮命中词并在无结果时提供清除筛选', async ({ page }) => {
  await page.goto('search/?q=MLIR');
  await expect(page.locator('.learning-search-item').first()).toBeVisible({ timeout: 10000 });
  await expect(page.locator('.learning-search-snippet mark.learning-hit').first()).toBeVisible();

  // 无意义查询 + 阶段筛选 → 无结果 → 提供清除筛选
  await page.fill('#learning-search-q', 'zzqqxx不存在的词');
  await page.selectOption('[data-learning="phase-select"]', '6');
  await page.click('button[type="submit"]');
  await expect(page.locator('.learning-search-empty')).toBeVisible({ timeout: 10000 });
  const clearButton = page.locator('.learning-search-empty button', { hasText: '清除筛选' });
  await expect(clearButton).toBeVisible();
  await clearButton.click();
  // 筛选已复位（查询词不变，仍无结果但筛选为空）
  await expect(page.locator('[data-learning="phase-select"]')).toHaveValue('');

  // 换回有效词后恢复结果
  await page.fill('#learning-search-q', 'MLIR');
  await page.click('button[type="submit"]');
  await expect(page.locator('.learning-search-item').first()).toBeVisible({ timeout: 10000 });
});
