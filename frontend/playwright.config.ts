import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  // Stop on first failure — faster feedback in dev
  maxFailures: 1,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    // Capture screenshot only on failure
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
