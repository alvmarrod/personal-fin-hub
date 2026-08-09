import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import DeleteProfileModal from './DeleteProfileModal.svelte';

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

describe('DeleteProfileModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('keeps the delete button disabled until the word DELETE is typed', async () => {
    render(DeleteProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    const delBtn = screen.getByRole('button', { name: 'Delete profile' });
    expect(delBtn.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText('DELETE'), { target: { value: 'DELET' } });
    expect(delBtn.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText('DELETE'), { target: { value: 'DELETE' } });
    expect(delBtn.disabled).toBe(false);
  });

  it('deletes the profile once confirmed', async () => {
    storeMock.deleteProfile.mockResolvedValue(undefined);
    const onclose = vi.fn();
    render(DeleteProfileModal, { props: { open: true, onclose, profile: PROFILE } });

    await fireEvent.input(screen.getByPlaceholderText('DELETE'), { target: { value: 'DELETE' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Delete profile' }));

    expect(storeMock.deleteProfile).toHaveBeenCalledWith(1);
    expect(onclose).toHaveBeenCalled();
  });

  it('uses the localized delete word in es-ES', async () => {
    setLocale('es-ES');
    render(DeleteProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });
    const delBtn = screen.getByRole('button', { name: 'Eliminar perfil' });
    expect(delBtn.disabled).toBe(true);

    await fireEvent.input(screen.getByPlaceholderText('BORRAR'), { target: { value: 'BORRAR' } });
    expect(delBtn.disabled).toBe(false);
  });

  it('shows last-profile error on 409', async () => {
    const err = new Error('409 conflict');
    err.status = 409;
    storeMock.deleteProfile.mockRejectedValue(err);
    render(DeleteProfileModal, { props: { open: true, onclose: vi.fn(), profile: PROFILE } });

    await fireEvent.input(screen.getByPlaceholderText('DELETE'), { target: { value: 'DELETE' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Delete profile' }));

    expect(await screen.findByText('You cannot delete the last remaining profile.')).toBeTruthy();
  });
});
