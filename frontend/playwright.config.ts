import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: process.env.LAB_URL || "http://127.0.0.1:8000",
    httpCredentials: process.env.LAB_PASSWORD
      ? {
          username: process.env.LAB_USERNAME || "operator",
          password: process.env.LAB_PASSWORD,
        }
      : undefined,
    browserName: "chromium",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 1050 },
    screenshot: "only-on-failure",
  },
});
