import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';

test('cloud readiness shows evidence, separate frameworks and editable reassessment', async ({ page }) => {
  await page.goto('/#cloud');
  await expect(page.getByRole('heading', { name: 'Cloud assurance, grounded in evidence.' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Bucket public-access baseline/ })).toBeVisible();
  await page.getByRole('button', { name: /Bucket public-access baseline/ }).click();
  await expect(page.getByText('One or more observed settings do not meet this project baseline.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'CSP Safety ↗' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'CSAP ↗', exact: true })).toBeVisible();
  await page.screenshot({ path: fileURLToPath(new URL('../../docs/screenshots/cloud-assurance.png', import.meta.url)), fullPage: true });
  await page.getByRole('button', { name: 'Edit evidence bundle' }).click();
  const editor = page.getByRole('textbox', { name: 'Synthetic evidence JSON' });
  const bundle = JSON.parse(await editor.inputValue());
  bundle.evidence.s3.data.PublicAccessBlockConfiguration.BlockPublicPolicy = true;
  await editor.fill(JSON.stringify(bundle));
  await page.getByRole('button', { name: 'Run readiness checks' }).click();
  await expect(page.getByText('Listed configuration checks match; human scope and operating-effectiveness review is still required.')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export review pack' }).click();
  expect((await download).suggestedFilename()).toBe('cloud-assurance-review.json');
  await page.goto('/#rag');
  await page.reload();
  await expect(page.getByText('CONTROL//ROOM', { exact: true })).toBeVisible();

});

test('invalid input clears stale assessment and mobile layout fits', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#cloud');
  await expect(page.getByRole('button', { name: /Root account MFA/ })).toBeVisible();
  await page.getByRole('button', { name: 'Edit evidence bundle' }).click();
  await page.getByRole('textbox', { name: 'Synthetic evidence JSON' }).fill('{ invalid');
  await expect(page.getByRole('button', { name: 'Export review pack' })).toBeDisabled();
  await page.getByRole('button', { name: 'Run readiness checks' }).click();
  await expect(page.getByRole('alert')).toContainText('Invalid JSON');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
