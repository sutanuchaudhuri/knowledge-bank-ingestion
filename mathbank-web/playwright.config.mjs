// End-to-end regression suite for mathbank-web (see requirements/23_E2E_REGRESSION_SUITE.md).
// Runs against an already running stack (`make up`); it never starts or stops services.
// Specs tagged @llm make paid model calls and only run when E2E_LLM=1.
import { defineConfig, devices } from "@playwright/test";

const runLlm = process.env.E2E_LLM === "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.mjs$/,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  grepInvert: runLlm ? undefined : /@llm/,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
