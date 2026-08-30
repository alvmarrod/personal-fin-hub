import { defineConfig, devices } from '@playwright/test';

const CI = !!process.env.CI;

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: CI ? 2 : 0,
  globalSetup: './e2e/cleanup.js',
  globalTeardown: './e2e/cleanup.js',
  use: {
    baseURL: 'http://localhost:5178',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'uv run uvicorn main:app --host 0.0.0.0 --port 8010',
      cwd: '../backend',
      port: 8010,
      reuseExistingServer: false,
      timeout: 15_000,
    },
    {
      command: 'bun run dev --host 0.0.0.0 --port 5178',
      cwd: '.',
      port: 5178,
      reuseExistingServer: false,
      timeout: 15_000,
      env: { VITE_API_TARGET: 'http://localhost:8010', VITE_DISABLE_TUTORIALS: '1' },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
