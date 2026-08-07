import { defineConfig, devices } from '@playwright/test';

const CI = !!process.env.CI;

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: CI ? 2 : 0,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'uv run uvicorn main:app --host 0.0.0.0 --port 8000',
      cwd: '../backend',
      port: 8000,
      reuseExistingServer: !CI,
      timeout: 15_000,
    },
    {
      command: 'bun run dev --host 0.0.0.0 --port 5173',
      cwd: '.',
      port: 5173,
      reuseExistingServer: !CI,
      timeout: 15_000,
      env: { VITE_API_TARGET: 'http://localhost:8000' },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
