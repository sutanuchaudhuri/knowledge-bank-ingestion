import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "local-auth.spec.ts",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5188", trace: "off" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    {
      command: "cd ../mathbank-rest && .venv/bin/python ../mathbank-socratic-admin/e2e/local_auth_server.py",
      url: "http://127.0.0.1:8018/openapi.json",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5188 --strictPort",
      env: { SOCRATIC_REST_TARGET: "http://127.0.0.1:8018" },
      url: "http://127.0.0.1:5188",
      reuseExistingServer: false,
    },
  ],
});
