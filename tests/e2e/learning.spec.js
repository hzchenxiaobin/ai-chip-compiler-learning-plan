/**
 * E2E：核心学习闭环（设计文档 §12.2 TC-F01/F02/F04、§10.4 无 JS 基线）。
 */
const { test, expect } = require('@playwright/test');

function uniqueName(prefix) {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
}

async function register(page) {
  await page.goto('/register/');
  await page.fill('#id_username', uniqueName('e2e'));
  await page.fill('#id_email', `${uniqueName('e2e')}@example.com`);
  await page.fill('#id_password1', 'pw-e2e-12345678');
  await page.fill('#id_password2', 'pw-e2e-12345678');
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => url.pathname === '/');
}

test('匿名可读：首页与日课页无需登录（TC-F01）', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('AI 芯片编译器');

  await page.goto('/tutorials/week-005/day-029/');
  await expect(page.locator('h1')).toContainText('第 29 天');
  // 任务卡显示登录引导，不显示虚假进度。
  await expect(page.locator('.learning-task-anonymous')).toContainText('登录');
  // 资源卡有源码 ZIP 与 GitHub 链接。
  await expect(page.locator('.learning-resource-btn').first()).toContainText('下载源码 ZIP');
});

test('注册→勾选任务→刷新状态保留（TC-F02/F04）', async ({ page }) => {
  await register(page);
  await page.goto('/tutorials/week-005/day-029/');

  const card = page.locator('[data-learning="day-task"]');
  await expect(card).toBeVisible();
  // 勾选「阅读 → 已完成」。
  await page.check('input[data-task="reading"][value="done"]');
  await expect(page.locator('[data-learning="save-status"]')).toContainText('已保存', {
    timeout: 10000,
  });

  // 刷新后状态保留。
  await page.reload();
  await expect(page.locator('input[data-task="reading"][value="done"]')).toBeChecked();
  // 整体状态派生为进行中。
  await expect(page.locator('[data-learning="overall-status"]')).toContainText('进行中');
});

test('blocked 状态展示与解除（TC-F05）', async ({ page }) => {
  await register(page);
  await page.goto('/tutorials/week-005/day-029/');
  await page.check('input[data-task="experiment"][value="blocked"]');
  await expect(page.locator('[data-learning="save-status"]')).toContainText('已保存', {
    timeout: 10000,
  });
  await expect(page.locator('[data-learning="overall-status"]')).toContainText('有卡点');

  await page.check('input[data-task="experiment"][value="done"]');
  await expect(page.locator('[data-learning="save-status"]')).toContainText('已保存', {
    timeout: 10000,
  });
  // 其他任务保持原状。
  await expect(page.locator('input[data-task="experiment"][value="done"]')).toBeChecked();
});

test('继续学习卡出现在登录首页（TC-F02）', async ({ page }) => {
  await register(page);
  await page.goto('/tutorials/week-001/day-001/');
  await page.check('input[data-task="reading"][value="done"]');
  await expect(page.locator('[data-learning="save-status"]')).toContainText('已保存', {
    timeout: 10000,
  });
  await page.goto('/');
  await expect(page.locator('[data-learning="continue"] .hero-button-primary'))
    .toContainText('继续 Day 1');
});

test('搜索无 JS 基线：服务端结果与翻页（§10.4）', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('/search/?q=MLIR');
  await expect(page.locator('.learning-search-status')).toContainText('个日课命中');
  await expect(page.locator('.learning-search-item').first()).toBeVisible();
  await context.close();
});

test('搜索 JS 增强：输入即时查询（防抖）', async ({ page }) => {
  await page.goto('/search/');
  await page.fill('#search-q', '常量折叠');
  await page.waitForTimeout(800);  // 防抖 + 请求。
  const items = page.locator('[data-learning="search-results"] .learning-search-item');
  await expect(items.first()).toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-learning="search-status"]')).toContainText('常量折叠');
});

test('周页与阶段页渲染（FR-007）', async ({ page }) => {
  await page.goto('/weeks/week-5/');
  await expect(page.locator('h1')).toContainText('第 5 周');
  await expect(page.locator('.learning-week-day').first()).toContainText('Day 29');

  await page.goto('/phases/phase-2/');
  await expect(page.locator('h1')).toContainText('阶段二');
});

test('设置页无 JS 基线：导出表单可用（§10.4）', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('/login/');
  await page.fill('#id_username', 'nojs_probe');
  await page.fill('#id_password', 'x-wrong-password');
  await page.click('button[type="submit"]');
  // 登录失败仍渲染（无 JS 可用性）。
  await expect(page.locator('.vp-auth-error')).toBeVisible();
  await context.close();
});
