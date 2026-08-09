import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import RenameProfileModal from './RenameProfileModal.svelte';

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

const PROFILE = { id: 1, name: 'Alpha', has_password: false };

describe('RenameProfileModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('pre-fills the current profile name', () => {
    render(RenameProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    expect(screen.getByPlaceholderText('Name').value).toBe('Alpha');
  });

  it('renames the profile', async () => {
    storeMock.renameProfile.mockResolvedValue({ id: 1, name: 'AlphaRenamed', has_password: false });
    const onclose = vi.fn();
    render(RenameProfileModal, { props: { open: true, onclose, profile: PROFILE } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: '  AlphaRenamed  ' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));

    expect(storeMock.renameProfile).toHaveBeenCalledWith(1, 'AlphaRenamed');
    expect(onclose).toHaveBeenCalled();
  });

  it('shows duplicate-name error on 409', async () => {
    const err = new Error('409 conflict');
    err.status = 409;
    storeMock.renameProfile.mockRejectedValue(err);
    render(RenameProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: 'Beta' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));

    expect(await screen.findByText('That name is already taken')).toBeTruthy();
  });

  it('requires a name', async () => {
    render(RenameProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: '   ' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
    expect(storeMock.renameProfile).not.toHaveBeenCalled();
    expect(screen.getByText('Profile name is required')).toBeTruthy();
  });
});
