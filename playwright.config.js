/**
 * Playwright 配置：对运行中的 Django 开发服务器执行 E2E。
 * 前置：manage.py runserver 127.0.0.1:8765（内容已导入激活）。
 */
module.exports = {
  testDir: './tests/e2e',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8765',
    headless: true,
    screenshot: 'only-on-failure',
    locale: 'zh-CN',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  reporter: [['list']],
};
