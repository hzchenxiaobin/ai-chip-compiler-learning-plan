import { test, expect } from '@playwright/test';

/**
 * 搜索 E2E（对应 docs/development/05 §5.2）：
 * 轻量搜索不加载正文分片；全文搜索按需加载并命中锚点；分片失败明确标注不完整。
 */

test('轻量搜索 MLIR 不请求正文分片', async ({ page }) => {
  const phaseRequests = [];
  page.on('request', (request) => {
    if (/phase-[1-6]\.json/.test(request.url())) phaseRequests.push(request.url());
  });
  await page.goto('search/?q=MLIR');
  await expect(page.locator('[data-learning="search-results"] .learning-search-item').first()).toBeVisible({ timeout: 10000 });
  expect(phaseRequests).toEqual([]);
});

test('全文搜索 run_all.sh 按需加载分片并给出结果', async ({ page }) => {
  await page.goto('search/');
  await page.fill('#learning-search-q', 'run_all.sh');
  await page.selectOption('[data-learning="scope-select"]', 'full');
  await page.click('button[type="submit"]');
  await expect(page.locator('[data-learning="search-results"] .learning-search-item').first()).toBeVisible({ timeout: 20000 });
  const first = page.locator('[data-learning="search-results"] .learning-search-item').first();
  const href = await first.getAttribute('href');
  expect(href).toMatch(/tutorials\/week-\d{3}\/day-\d{3}\/$/);
});

test('分片失败时保留轻量结果并提示不完整', async ({ page }) => {
  await page.route(/phase-[1-6]\.json/, (route) => route.abort());
  await page.goto('search/?q=MLIR');
  await expect(page.locator('[data-learning="search-results"] .learning-search-item').first()).toBeVisible({ timeout: 10000 });
  await page.selectOption('[data-learning="scope-select"]', 'full');
  await page.click('button[type="submit"]');
  await expect(page.locator('[data-learning="phase-status"]')).toContainText(/失败|不完整/, { timeout: 20000 });
});
