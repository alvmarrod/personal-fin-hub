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

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  try {
    await page.goto('/profiles');
    await page.locator('.profile-card').first().waitFor({ state: 'visible', timeout: 20000 });
    await page.locator('.profile-card').first().click();
    await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 15000 });
  } catch {
    await page.screenshot({ path: 'test-results/auth-failed.png', fullPage: true });
    throw new Error('Authentication failed — profile card not found or click did not lead to app shell');
  } finally {
    await page.close();
  }
});

for (const { path, title } of pages) {
  test(`page "${title}" loads`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 20000 });
    await expect(page.locator('.app-content h1')).toContainText(title);
  });
}
