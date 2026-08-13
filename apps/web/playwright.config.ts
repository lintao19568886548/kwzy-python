import { defineConfig } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "e2e",
  timeout: 120000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  // 禁止依赖外部已启动服务；stack 由 globalSetup 拉起
  webServer: undefined,
});
