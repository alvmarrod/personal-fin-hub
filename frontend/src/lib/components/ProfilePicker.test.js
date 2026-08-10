import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, waitFor, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import ProfilePicker from './ProfilePicker.svelte';

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

const PROFILES = [
  { id: 1, name: 'Alpha', has_password: false },
  { id: 2, name: 'Beta', has_password: true },
];

describe('ProfilePicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('shows loading state initially', async () => {
    let resolveLoad;
    storeMock.loadProfiles.mockReturnValue(new Promise((r) => { resolveLoad = r; }));
    storeMock.profiles.mockReturnValue([]);

    render(ProfilePicker);
    expect(screen.getByText('Loading...')).toBeTruthy();

    resolveLoad([]);
    await waitFor(() => expect(screen.queryByText('Loading...')).toBeNull());
  });

  it('lists profiles with passwordless and password-protected markers', async () => {
    storeMock.profiles.mockReturnValue(PROFILES);
    storeMock.loadProfiles.mockResolvedValue(PROFILES);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('Alpha')).toBeTruthy());
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByText('Password protected')).toBeTruthy();
  });

  it('activates a passwordless profile on click', async () => {
    storeMock.profiles.mockReturnValue(PROFILES);
    storeMock.loadProfiles.mockResolvedValue(PROFILES);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('Alpha')).toBeTruthy());

    const alphaCard = screen.getByText('Alpha').closest('button');
    await fireEvent.click(alphaCard);

    expect(storeMock.activateProfile).toHaveBeenCalledWith(PROFILES[0]);
  });

  it('opens unlock modal for a password-protected profile', async () => {
    storeMock.profiles.mockReturnValue(PROFILES);
    storeMock.loadProfiles.mockResolvedValue(PROFILES);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('Beta')).toBeTruthy());

    const betaCard = screen.getByText('Beta').closest('button');
    await fireEvent.click(betaCard);

    expect(storeMock.activateProfile).not.toHaveBeenCalled();
    expect(screen.getByText('Unlock Beta')).toBeTruthy();
  });

  it('shows empty state when no profiles exist', async () => {
    storeMock.profiles.mockReturnValue([]);
    storeMock.loadProfiles.mockResolvedValue([]);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('No profiles yet')).toBeTruthy());
  });

  it('shows error state with retry button on load failure', async () => {
    storeMock.loadProfiles.mockRejectedValue(new Error('network'));
    storeMock.profiles.mockReturnValue([]);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('Retry')).toBeTruthy()); // eslint-disable-line no-unused-expressions
    expect(screen.getByText('network')).toBeTruthy();

    storeMock.loadProfiles.mockResolvedValue(PROFILES);
    storeMock.profiles.mockReturnValue(PROFILES);
    await fireEvent.click(screen.getByText('Retry'));

    await waitFor(() => expect(screen.getByText('Alpha')).toBeTruthy());
  });

  it('opens create profile modal on create click', async () => {
    storeMock.profiles.mockReturnValue(PROFILES);
    storeMock.loadProfiles.mockResolvedValue(PROFILES);

    render(ProfilePicker);
    await waitFor(() => expect(screen.getByText('Alpha')).toBeTruthy());

    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(screen.getByText('New Profile')).toBeTruthy();
  });
});
