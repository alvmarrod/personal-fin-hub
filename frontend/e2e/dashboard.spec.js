import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 800 } });

const pages = [
  { path: '/', title: 'Dashboard' },
  { path: '/transactions', title: 'Transactions' },
  { path: '/performance', title: 'Performance' },
  { path: '/income', title: 'Income' },
  { path: '/cash-flow', title: 'Cash Flow' },
  { path: '/dividends', title: 'Dividends' },
  { path: '/entities', title: 'Entities' },
  { path: '/currencies', title: 'Currencies' },
  { path: '/market-assets', title: 'Market Assets' },
  { path: '/portfolio-assets', title: 'Portfolio Assets' },
  { path: '/schedules', title: 'Schedules' },
  { path: '/transfers/new', title: 'Transfer' },
  { path: '/balance-snapshots', title: 'Balance Snapshots' },
  { path: '/fiscal-exemptions', title: 'Fiscal Exemptions' },
];

test.beforeEach(async ({ page }) => {
  await page.goto('/profiles');
  await page.locator('.profile-card').first().waitFor({ state: 'visible', timeout: 10000 }).then(async () => {
    await page.locator('.profile-card').first().click();
    await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 5000 });
  }).catch(() => {
    // profiles not available or app shell already visible (active session restored)
  });
});

for (const { path, title } of pages) {
  test(`page "${title}" loads`, async ({ page }) => {
    await page.goto(path);
    await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 10000 });
    await expect(page.locator('.app-content h1')).toContainText(title);
  });
}
