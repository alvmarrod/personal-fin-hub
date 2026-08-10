import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const { apiMock, setActiveProfileId } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
  },
  setActiveProfileId: vi.fn(),
}));

vi.mock('$lib/api/client.js', () => ({
  api: apiMock,
  setActiveProfileId,
}));

const STORAGE_KEY = 'pfh:activeProfileId';

let store;

async function freshStore() {
  vi.resetModules();
  store = await import('./profile.svelte.js');
}

function seedProfiles() {
  apiMock.get.mockResolvedValue([
    { id: 1, name: 'Alpha', has_password: false },
    { id: 2, name: 'Beta', has_password: true },
  ]);
}

describe('profile store', () => {
  beforeEach(async () => {
    await freshStore();
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    store?.logout();
  });

  it('loads profiles into state', async () => {
    seedProfiles();
    await store.loadProfiles();
    expect(store.profiles()).toHaveLength(2);
    expect(apiMock.get).toHaveBeenCalledWith('/profiles');
  });

  it('starts without an active profile', () => {
    expect(store.hasActiveProfile()).toBe(false);
    expect(store.activeProfile()).toBeNull();
    expect(store.activeProfileName()).toBeNull();
  });

  it('activateProfile sets active, persists id, and notifies the api client', () => {
    store.activateProfile({ id: 7, name: 'Gamma' });
    expect(store.activeProfile()).toEqual({ id: 7, name: 'Gamma' });
    expect(store.activeProfileName()).toBe('Gamma');
    expect(store.hasActiveProfile()).toBe(true);
    expect(setActiveProfileId).toHaveBeenCalledWith(7);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('7');
  });

  it('logout clears active, storage, and api client', () => {
    store.activateProfile({ id: 7, name: 'Gamma' });
    store.logout();
    expect(store.hasActiveProfile()).toBe(false);
    expect(setActiveProfileId).toHaveBeenCalledWith(null);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('initProfiles restores a stored active profile', async () => {
    seedProfiles();
    sessionStorage.setItem(STORAGE_KEY, '2');
    await store.initProfiles();
    expect(store.hasActiveProfile()).toBe(true);
    expect(store.activeProfile()).toEqual({ id: 2, name: 'Beta' });
    expect(setActiveProfileId).toHaveBeenCalledWith(2);
  });

  it('initProfiles clears a stale stored profile id', async () => {
    seedProfiles();
    sessionStorage.setItem(STORAGE_KEY, '99');
    await store.initProfiles();
    expect(store.hasActiveProfile()).toBe(false);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('initProfiles keeps the stored session when the list load fails', async () => {
    apiMock.get.mockRejectedValue(new Error('network'));
    sessionStorage.setItem(STORAGE_KEY, '2');
    await store.initProfiles();
    expect(store.hasActiveProfile()).toBe(false);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('2');
  });

  it('initProfiles runs its restore logic only once', async () => {
    seedProfiles();
    sessionStorage.setItem(STORAGE_KEY, '2');
    await store.initProfiles();
    store.logout();
    sessionStorage.setItem(STORAGE_KEY, '1');
    await store.initProfiles();
    expect(store.hasActiveProfile()).toBe(false);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('1');
  });

  it('unlockProfile unlocks, activates, and refreshes the list', async () => {
    seedProfiles();
    apiMock.post.mockResolvedValue({ id: 2, name: 'Beta', has_password: true });
    await store.unlockProfile({ id: 2, name: 'Beta' }, 'secret');
    expect(apiMock.post).toHaveBeenCalledWith('/profiles/2/unlock', { password: 'secret' });
    expect(store.activeProfile()).toEqual({ id: 2, name: 'Beta' });
    expect(apiMock.get).toHaveBeenCalledWith('/profiles');
  });

  it('createProfile creates, refreshes, and activates the new profile', async () => {
    seedProfiles();
    apiMock.post.mockResolvedValue({ id: 3, name: 'New', has_password: false });
    await store.createProfile('New', 'pw');
    expect(apiMock.post).toHaveBeenCalledWith('/profiles', { name: 'New', password: 'pw' });
    expect(store.activeProfileName()).toBe('New');
  });

  it('renameProfile refreshes and updates the active profile name', async () => {
    seedProfiles();
    store.activateProfile({ id: 1, name: 'Alpha' });
    apiMock.patch.mockResolvedValue({ id: 1, name: 'AlphaRenamed', has_password: false });
    await store.renameProfile(1, 'AlphaRenamed');
    expect(apiMock.patch).toHaveBeenCalledWith('/profiles/1', { name: 'AlphaRenamed' });
    expect(store.activeProfile()).toEqual({ id: 1, name: 'AlphaRenamed' });
  });

  it('deleteProfile clears the session when deleting the active profile', async () => {
    seedProfiles();
    store.activateProfile({ id: 1, name: 'Alpha' });
    apiMock.del.mockResolvedValue(null);
    await store.deleteProfile(1);
    expect(apiMock.del).toHaveBeenCalledWith('/profiles/1');
    expect(store.hasActiveProfile()).toBe(false);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('deleteProfile keeps the session when deleting another profile', async () => {
    seedProfiles();
    store.activateProfile({ id: 1, name: 'Alpha' });
    apiMock.del.mockResolvedValue(null);
    await store.deleteProfile(2);
    expect(store.hasActiveProfile()).toBe(true);
    expect(store.activeProfile()).toEqual({ id: 1, name: 'Alpha' });
  });
});
