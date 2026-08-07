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

for (const { path, title } of pages) {
  test(`page "${title}" loads`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('h1')).toContainText(title);
  });
}
