import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    headless: true,
  },
  webServer: process.env.E2E_SKIP_WEBSERVER
    ? undefined
    : {
        command: "npm run dev -- --host 127.0.0.1 --port 5173",
        url: "http://127.0.0.1:5173",
        reuseExistingServer: true,
        timeout: 120000,
      },
});
