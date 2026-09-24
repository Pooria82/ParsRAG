import { defineConfig, devices } from '@playwright/test';

const externalBaseURL = process.env.PWA_TEST_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'pwa.spec.ts',
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: externalBaseURL ?? 'http://127.0.0.1:4180',
    ...devices['Desktop Chrome'],
    ...(process.env.CI ? {} : { channel: 'chrome' }),
  },
  webServer: externalBaseURL ? undefined : {
    command: 'npm run preview -- --host 127.0.0.1 --port 4180 --strictPort',
    url: 'http://127.0.0.1:4180',
    reuseExistingServer: !process.env.CI,
  },
});
