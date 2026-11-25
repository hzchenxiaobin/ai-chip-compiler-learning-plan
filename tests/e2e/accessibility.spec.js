/**
 * 无障碍验收（设计文档 §10.2 / TC-A01—A03）：
 * - 键盘可达：Tab 进入跳转链接与主导航；
 * - 320px 无横向溢出（TC-A02）；
 * - 双主题可切换（TC-A03）；
 * - axe-core 扫描（经 CDN 注入；网络不可用时跳过并提示）。
 */
const { test, expect } = require('@playwright/test');

async function register(page) {
  await page.goto('/register/');
  await page.fill('#id_username', `a11e_${Date.now()}_${Math.floor(Math.random() * 999)}`);
  await page.fill('#id_email', `a11e${Date.now()}@example.com`);
  await page.fill('#id_password1', 'pw-a11e-12345678');
  await page.fill('#id_password2', 'pw-a11e-12345678');
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => url.pathname === '/');
}

const PAGES = [
  '/',
  '/plan/',
  '/tutorials/week-001/day-001/',
  '/tutorials/week-005/day-029/',
  '/weeks/week-5/',
  '/phases/phase-2/',
  '/search/?q=MLIR',
  '/login/',
];

test('键盘可达：跳到正文与主导航（TC-A01）', async ({ page }) => {
  await page.goto('/tutorials/week-005/day-029/', { waitUntil: 'domcontentloaded' });
  // 跳转链接是第一个可聚焦元素。
  await page.keyboard.press('Tab');
  const active = await page.evaluate(() => {
    const el = document.activeElement;
    return { tag: el && el.tagName, cls: el ? String(el.className) : '' };
  });
  expect(active.cls, `首个 Tab 焦点：${active.tag}.${active.cls}`).toContain('skip-link');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(150);
  // 锚点跳转生效：URL hash 指向正文且页面滚动。
  const hash = await page.evaluate(() => window.location.hash);
  expect(hash).toBe('#main-content');
  const scrolled = await page.evaluate(() => window.scrollY > 0);
  expect(scrolled).toBe(true);
});

test('任务卡可键盘操作（TC-A01）', async ({ page }) => {
  await register(page);
  await page.goto('/tutorials/week-005/day-029/', { waitUntil: 'domcontentloaded' });
  const radio = page.locator('input[data-task="reading"][value="done"]');
  await radio.focus();
  await expect(radio).toBeFocused();
  await radio.press('Space');
  await expect(page.locator('input[data-task="reading"][value="done"]')).toBeChecked();
});

test('320px 无横向溢出（TC-A02）', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  for (const path of PAGES) {
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow, `${path} 横向溢出 ${overflow}px`).toBeLessThanOrEqual(1);
  }
});

test('200% 字体缩放不丢失内容（TC-A02）', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/tutorials/week-005/day-029/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%';
  });
  await expect(page.locator('h1')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth
  );
  // 允许纵向滚动；横向不整页溢出。
  expect(overflow).toBeLessThanOrEqual(8);
});

test('明暗主题切换（TC-A03）', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const initial = await page.evaluate(() =>
    document.documentElement.classList.contains('dark')
  );
  await page.click('.vp-appearance .vp-switch');
  const switched = await page.evaluate(() =>
    document.documentElement.classList.contains('dark')
  );
  expect(switched).not.toBe(initial);
});

test.describe('axe-core 扫描（CDN 注入）', () => {
  for (const path of PAGES) {
    test(`axe: ${path}`, { timeout: 90000 }, async ({ page }) => {
      await page.goto(path, { waitUntil: 'domcontentloaded' });
      let injected = true;
      try {
        await page.addScriptTag({
          url: 'https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js',
          timeout: 45000,
        });
      } catch (error) {
        injected = false;
        test.skip(true, 'CDN 不可达，跳过 axe 扫描');
      }
      if (!injected) return;
      const results = await page.evaluate(async () => {
        const run = await window.axe.run(document, {
          resultTypes: ['violations'],
        });
        return {
          violations: run.violations
            .filter((v) => ['critical', 'serious'].includes(v.impact))
            .map((v) => `${v.id}(${v.impact}): ${v.help}`),
        };
      });
      // 阻断 critical/serious 违规（moderate 记录供评审）。
      const text = results.violations.join('; ');
      expect(text, `axe critical/serious 违规：${text}`).toBe('');
    });
  }
});
