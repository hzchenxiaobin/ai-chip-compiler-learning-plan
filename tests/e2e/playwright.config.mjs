import { defineConfig } from '@playwright/test';

/**
 * E2E 配置：对同一 public/ 产物在项目子路径下测试（与 Pages 一致）。
 * 前置：LEARNING_BASE_PATH=/ai-chip-compiler-learning-plan python3 tools/build.py
 */

const PORT = process.env.E2E_PORT || 8000;
const BASE_URL = `http://127.0.0.1:${PORT}/ai-chip-compiler-learning-plan/`;

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.mjs/,
  timeout: 30000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: BASE_URL,
    headless: true,
  },
  webServer: {
    command: `python3 ${import.meta.dirname}/serve.py ${import.meta.dirname}/../../public ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 20000,
  },
});
