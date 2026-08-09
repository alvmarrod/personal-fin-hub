import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Header from './Header.svelte';

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

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('shows the active profile name and initial', () => {
    storeMock.activeProfileName.mockReturnValue('Alpha');
    render(Header);
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('A')).toBeTruthy();
  });

  it('opens a dropdown with switch and logout on profile button click', async () => {
    storeMock.activeProfileName.mockReturnValue('Alpha');
    render(Header);

    await fireEvent.click(screen.getByText('Alpha'));

    expect(screen.getByText('Switch profile')).toBeTruthy();
    expect(screen.getByText('Log out')).toBeTruthy();
  });

  it('calls logout when switch profile is clicked', async () => {
    storeMock.activeProfileName.mockReturnValue('Alpha');
    render(Header);

    await fireEvent.click(screen.getByText('Alpha'));
    await fireEvent.click(screen.getByText('Switch profile'));

    expect(storeMock.logout).toHaveBeenCalled();
  });

  it('calls logout when log out is clicked', async () => {
    storeMock.activeProfileName.mockReturnValue('Alpha');
    render(Header);

    await fireEvent.click(screen.getByText('Alpha'));
    await fireEvent.click(screen.getByText('Log out'));

    expect(storeMock.logout).toHaveBeenCalled();
  });

  it('shows empty avatar when no profile is active', () => {
    storeMock.activeProfileName.mockReturnValue(null);
    const { container } = render(Header);
    const avatar = container.querySelector('.profile-avatar');
    expect(avatar?.textContent).toBe('');
  });
});
