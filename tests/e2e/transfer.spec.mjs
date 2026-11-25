import { test, expect } from '@playwright/test';

/**
 * 导入导出与清空 E2E（对应 docs/development/05 §5.2）：
 * 坏文件预检后数据库不变；导出触发下载；清空二次确认后计数为 0。
 */

test('设置页显示持久存储状态', async ({ page }) => {
  await page.goto('settings/');
  await expect(page.locator('[data-learning="storage-status"]')).toContainText('此浏览器', { timeout: 10000 });
});

test('坏 JSON 导入被整批拒绝且不改变现有记录', async ({ page }) => {
  // 先写入一条真实记录
  await page.goto('tutorials/week-005/day-029/');
  await page.locator('fieldset[data-task-id="reading"] input[value="done"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('settings/');
  const badFile = {
    name: 'bad.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{not valid json', 'utf-8'),
  };
  await page.setInputFiles('[data-learning="import-file"]', badFile);
  await page.click('[data-learning="import-form"] button[type="submit"]');
  await expect(page.locator('[data-learning="import-result"]')).toContainText('失败', { timeout: 10000 });

  await page.goto('tutorials/week-005/day-029/');
  await expect(page.locator('fieldset[data-task-id="reading"] input[value="done"]')).toBeChecked();
});

test('导出触发文件下载', async ({ page }) => {
  await page.goto('settings/');
  const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
  await page.click('[data-learning="export-button"]');
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^ai-chip-compiler-learning-backup-\d{8}\.json$/);
});

test('清空学习记录需二次确认且结果为 0', async ({ page }) => {
  await page.goto('tutorials/week-005/day-029/');
  await page.locator('fieldset[data-task-id="reading"] input[value="done"]').check();
  await expect(page.locator('[data-learning="save-state"]')).toContainText('已保存', { timeout: 10000 });

  await page.goto('settings/');
  const clearButton = page.locator('[data-learning="clear-progress"]');
  await clearButton.click();
  await expect(clearButton).toContainText('确认清空');
  await clearButton.click();
  await expect(page.locator('[data-learning="clear-result"]')).toContainText('已清空', { timeout: 10000 });
  await expect(page.locator('[data-learning="storage-status"]')).toContainText('已有记录：0 天', { timeout: 10000 });
});
