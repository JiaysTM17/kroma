import { defineConfig, devices } from '@playwright/test';

const pwChannel = process.env.PW_CHANNEL as 'chrome' | 'msedge' | undefined;

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [
    ['list'],
    ['html', { outputFolder: './playwright-report', open: 'never' }],
  ],
  globalSetup: './globalSetup.ts',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3005',
    navigationTimeout: 30_000,
    actionTimeout: 15_000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    acceptDownloads: true,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(pwChannel ? { channel: pwChannel } : {}),
      },
    },
  ],
});
