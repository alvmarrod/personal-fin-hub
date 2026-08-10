import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import UnlockProfileModal from './UnlockProfileModal.svelte';

const { storeMock } = vi.hoisted(() => ({
  storeMock: {
    profiles: vi.fn(() => []),
    loadProfiles: vi.fn(() => Promise.resolve()),
    activateProfile: vi.fn(),
    createProfile: vi.fn(),
    unlockProfile: vi.fn(),
    renameProfile: vi.fn(),
    deleteProfile: vi.fn(),
    logout: vi.fn(),
    activeProfileName: vi.fn(() => null),
  },
}));

vi.mock('$lib/stores/profile.svelte.js', () => ({
  profiles: storeMock.profiles,
  loadProfiles: storeMock.loadProfiles,
  activateProfile: storeMock.activateProfile,
  createProfile: storeMock.createProfile,
  unlockProfile: storeMock.unlockProfile,
  renameProfile: storeMock.renameProfile,
  deleteProfile: storeMock.deleteProfile,
  logout: storeMock.logout,
  activeProfileName: storeMock.activeProfileName,
}));

const PROFILE = { id: 2, name: 'Beta', has_password: true };

describe('UnlockProfileModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('disables unlock until a password is typed', () => {
    render(UnlockProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    const unlockBtn = screen.getByRole('button', { name: 'Unlock' });
    expect(unlockBtn.disabled).toBe(true);
  });

  it('unlocks the profile with the typed password', async () => {
    storeMock.unlockProfile.mockResolvedValue({ ...PROFILE });
    const { container } = render(UnlockProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });

    await fireEvent.input(container.querySelector('input[type="password"]'), { target: { value: 'secret' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Unlock' }));

    expect(storeMock.unlockProfile).toHaveBeenCalledWith(PROFILE, 'secret');
  });

  it('shows invalid password error on 401', async () => {
    const err = new Error('wrong password');
    err.status = 401;
    storeMock.unlockProfile.mockRejectedValue(err);
    const { container } = render(UnlockProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });

    await fireEvent.input(container.querySelector('input[type="password"]'), { target: { value: 'nope' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Unlock' }));

    expect(await screen.findByText('Wrong password')).toBeTruthy();
    expect(storeMock.activateProfile).not.toHaveBeenCalled();
  });

  it('shows the profile name in the title', () => {
    render(UnlockProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    expect(screen.getByRole('dialog').getAttribute('aria-label')).toContain('Beta');
  });
});
