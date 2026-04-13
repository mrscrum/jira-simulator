import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "test-boxplot.spec.ts",
  timeout: 30000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
