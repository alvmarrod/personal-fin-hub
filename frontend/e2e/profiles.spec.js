import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 800 } });

test('profile lifecycle: create -> switch -> logout -> delete', async ({ page }) => {
  const profileName = `E2E-${Date.now()}`;

  // 1. Create a profile from the picker screen.
  await page.goto('/profiles');
  await page.locator('.picker-shell').waitFor({ state: 'visible', timeout: 20000 });

  await page.getByRole('button', { name: 'Create profile' }).click();
  const createDialog = page.getByRole('dialog', { name: 'New Profile' });
  await createDialog.waitFor({ state: 'visible' });
  await createDialog.getByPlaceholder('Name').fill(profileName);
  await createDialog.getByRole('button', { name: 'Create profile' }).click();

  await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 15000 });
  await expect(page.locator('.header .profile-name')).toHaveText(profileName, { timeout: 15000 });

  // 2. Switch profile (logs out to the picker), then pick another profile.
  await page.locator('.profile-btn').click();
  await page.getByRole('menu').waitFor({ state: 'visible' });
  await page.getByRole('menuitem', { name: 'Switch profile' }).click();
  await page.locator('.picker-shell').waitFor({ state: 'visible', timeout: 15000 });

  await page.locator('.profile-card', { hasNotText: profileName }).first().click();
  await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 15000 });

  // 3. Log out explicitly, then re-enter through the picker.
  await page.locator('.profile-btn').click();
  await page.getByRole('menu').waitFor({ state: 'visible' });
  await page.getByRole('menuitem', { name: 'Log out' }).click();
  await page.locator('.picker-shell').waitFor({ state: 'visible', timeout: 15000 });

  await page.locator('.profile-card', { hasNotText: profileName }).first().click();
  await page.locator('.app-shell').waitFor({ state: 'attached', timeout: 15000 });

  // 4. Delete the created profile from Settings via the two-stage confirm.
  await page.goto('/settings');
  const row = page.locator('.profile-manage-row', { hasText: profileName });
  await expect(row).toHaveCount(1, { timeout: 15000 });

  await row.getByRole('button', { name: 'Delete' }).click();
  const confirmDialog = page.getByRole('dialog', { name: 'Delete Profile' });
  await confirmDialog.getByRole('button', { name: 'Delete' }).click();

  const typeInput = page.getByPlaceholder('DELETE');
  await typeInput.waitFor({ state: 'visible' });
  await typeInput.fill('DELETE');
  await page.getByRole('dialog', { name: 'Delete Profile' }).getByRole('button', { name: 'Delete profile' }).click();

  await expect(row).toHaveCount(0, { timeout: 15000 });
});
