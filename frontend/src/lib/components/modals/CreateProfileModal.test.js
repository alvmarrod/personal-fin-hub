import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import CreateProfileModal from './CreateProfileModal.svelte';

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

describe('CreateProfileModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('creates a profile with name and password', async () => {
    storeMock.createProfile.mockResolvedValue({ id: 3, name: 'Gamma', has_password: false });
    const onclose = vi.fn();
    const { container } = render(CreateProfileModal, { props: { open: true, onclose } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: '  Gamma  ' } });
    await fireEvent.input(container.querySelector('input[type="password"]'), { target: { value: 'pw' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));

    expect(storeMock.createProfile).toHaveBeenCalledWith('Gamma', 'pw');
  });

  it('sends null password when left empty', async () => {
    storeMock.createProfile.mockResolvedValue({ id: 3, name: 'Gamma', has_password: false });
    const onclose = vi.fn();
    render(CreateProfileModal, { props: { open: true, onclose } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: 'Gamma' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));

    expect(storeMock.createProfile).toHaveBeenCalledWith('Gamma', null);
  });

  it('requires a name', async () => {
    const onclose = vi.fn();
    render(CreateProfileModal, { props: { open: true, onclose } });

    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));

    expect(storeMock.createProfile).not.toHaveBeenCalled();
    expect(screen.getByText('Profile name is required')).toBeTruthy();
  });

  it('surfaces duplicate-name error on 409', async () => {
    const err = new Error('409 conflict');
    err.status = 409;
    storeMock.createProfile.mockRejectedValue(err);
    render(CreateProfileModal, { props: { open: true, onclose: vi.fn() } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: 'Alpha' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));

    expect(await screen.findByText('That name is already taken')).toBeTruthy();
  });

  it('calls onclose after successful creation', async () => {
    storeMock.createProfile.mockResolvedValue({ id: 3, name: 'Gamma', has_password: false });
    const onclose = vi.fn();
    render(CreateProfileModal, { props: { open: true, onclose } });

    await fireEvent.input(screen.getByPlaceholderText('Name'), { target: { value: 'Gamma' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));

    expect(onclose).toHaveBeenCalled();
  });

  it('renders nothing when closed', () => {
    const { container } = render(CreateProfileModal, { props: { open: false, onclose: vi.fn() } });
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });
});
