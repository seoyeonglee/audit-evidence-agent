import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1,
  reporter: [['list'], ['json', { outputFile: fileURLToPath(new URL('../docs/reports/browser-tests.json', import.meta.url)) }]],
  use: { baseURL: 'http://localhost:5173', viewport: { width: 1512, height: 1120 }, trace: 'retain-on-failure' },
  webServer: [
    { command: `${process.env.PYTHON_BIN ?? 'python'} -m uvicorn src.api:app --host 127.0.0.1 --port 8000`, cwd: '..',
      url: 'http://localhost:8000/health', reuseExistingServer: !process.env.CI, timeout: 60000,
      env: { DEMO_MODE: '1', DATABASE_URL: process.env.E2E_DATABASE_URL ?? 'sqlite:///e2e-operations.db' } },
    { command: 'npm run dev -- --host 127.0.0.1', url: 'http://localhost:5173', reuseExistingServer: !process.env.CI, timeout: 60000 },
  ],
});
