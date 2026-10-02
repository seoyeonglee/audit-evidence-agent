import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';
const screenshot = (name: string) => fileURLToPath(new URL(`../../docs/screenshots/${name}`, import.meta.url));

test('evidence submission, worker processing, source inspection and approval', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Evidence operations' })).toBeVisible();
  await page.getByLabel('Demo persona').selectOption('owner');
  await expect(page.getByRole('button', { name: /Quarterly privileged access review/ })).toBeVisible();
  await page.getByRole('button', { name: 'Submit sample evidence' }).click();
  await expect(page.getByText('Evidence accepted. A durable processing job was queued.')).toBeVisible();
  await page.getByLabel('Demo persona').selectOption('reviewer');
  await page.getByRole('button', { name: 'Process queued documents' }).click();
  await expect(page.getByText('production-admin', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('✓ Source verified', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: screenshot('operations.png'), fullPage: true });
  await page.getByLabel('Reviewer feedback').fill('Verified source fields, scope and review period.');
  await page.getByRole('button', { name: 'Approve record' }).click();
  await expect(page.getByText('Review recorded: approved.')).toBeVisible();
  await expect(page.getByTestId('request-status')).toHaveText('APPROVED');
  await expect(page.getByText('review.approve', { exact: true })).toBeVisible();
  await page.screenshot({ path: screenshot('approved-record.png'), fullPage: true });
});

test('external vendor scope is enforced and reviewer actions are hidden', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Demo persona').selectOption('vendor');
  await expect(page.getByRole('button', { name: /Vendor security attestation/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Quarterly privileged access review/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Approve record' })).toHaveCount(0);
  await page.screenshot({ path: screenshot('vendor-scope.png'), fullPage: true });
});

test('another organization has only its own records; mobile layout has no overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByLabel('Demo persona').selectOption('other-reviewer');
  await expect(page.getByRole('button', { name: /Restricted organization record/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Quarterly privileged access review/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: screenshot('mobile.png'), fullPage: true });
});
