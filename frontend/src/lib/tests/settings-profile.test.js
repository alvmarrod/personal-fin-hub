import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, waitFor, cleanup, within } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import * as store from '$lib/stores/profile.svelte.js';
import Page from '../../routes/settings/+page.svelte';

const { apiMock } = vi.hoisted(() => {
  let profiles = [{ id: 1, name: 'Default', has_password: false }];
  let nextId = 2;
  const clone = (p) => ({ id: p.id, name: p.name, has_password: p.has_password });
  return {
    apiMock: {
      get: vi.fn(async (path) => {
        if (path === '/profiles') return profiles.map(clone);
        if (path === '/currencies') return ['EUR', 'USD'];
        throw new Error('unexpected GET ' + path);
      }),
      post: vi.fn(async (path, data) => {
        if (path === '/profiles') {
          const created = { id: nextId++, name: data.name, has_password: Boolean(data.password) };
          profiles.push(created);
          return clone(created);
        }
        throw new Error('unexpected POST ' + path);
      }),
      patch: vi.fn(async (path, data) => {
        const id = Number(path.split('/').pop());
        const p = profiles.find((x) => x.id === id);
        if (!p) throw Object.assign(new Error('not found'), { status: 404 });
        p.name = data.name;
        return clone(p);
      }),
      del: vi.fn(async (path) => {
        const id = Number(path.split('/').pop());
        const idx = profiles.findIndex((x) => x.id === id);
        if (idx >= 0) profiles.splice(idx, 1);
        return null;
      }),
      __seed(next) {
        profiles = next.map(clone);
        nextId = Math.max(...next.map((p) => p.id)) + 1;
      },
      __list() {
        return profiles.map(clone);
      },
    },
  };
});

vi.mock('$lib/api/client.js', () => ({
  api: apiMock,
  setActiveProfileId: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  },
}));

describe('Settings profile management', () => {
  beforeEach(async () => {
    apiMock.__seed([{ id: 1, name: 'Default', has_password: false }]);
    store.logout();
    sessionStorage.clear();
    await store.loadProfiles();
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('renders existing profiles and marks the active one as Current', async () => {
    apiMock.__seed([
      { id: 1, name: 'Default', has_password: false },
      { id: 2, name: 'Family', has_password: true },
    ]);
    await store.loadProfiles();
    store.activateProfile({ id: 1, name: 'Default' });

    render(Page);
    await waitFor(() => expect(screen.getByText('Default')).toBeTruthy());
    expect(screen.getByText('Family')).toBeTruthy();

    const defaultRow = screen.getByText('Default').closest('.profile-manage-row');
    expect(within(defaultRow).getByText('Current')).toBeTruthy();

    const familyRow = screen.getByText('Family').closest('.profile-manage-row');
    expect(within(familyRow).queryByText('Current')).toBeNull();
  });

  it('creates a profile via the modal and activates it', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Default')).toBeTruthy());

    await fireEvent.click(screen.getByRole('button', { name: 'Create profile' }));
    const dialog = await screen.findByRole('dialog', { name: 'New Profile' });
    await fireEvent.input(within(dialog).getByPlaceholderText('Name'), { target: { value: 'Gamma' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Create profile' }));

    await waitFor(() => expect(screen.getByText('Gamma')).toBeTruthy());
    expect(apiMock.post).toHaveBeenCalledWith('/profiles', { name: 'Gamma', password: null });

    const gammaRow = screen.getByText('Gamma').closest('.profile-manage-row');
    await waitFor(() => expect(within(gammaRow).getByText('Current')).toBeTruthy());
  });

  it('renames a profile through the rename modal', async () => {
    apiMock.__seed([
      { id: 1, name: 'Default', has_password: false },
      { id: 2, name: 'Family', has_password: false },
    ]);
    await store.loadProfiles();

    render(Page);
    await waitFor(() => expect(screen.getByText('Family')).toBeTruthy());

    const familyRow = screen.getByText('Family').closest('.profile-manage-row');
    await fireEvent.click(within(familyRow).getByRole('button', { name: 'Rename' }));

    const dialog = await screen.findByRole('dialog', { name: 'Rename Profile' });
    await fireEvent.input(within(dialog).getByPlaceholderText('Name'), { target: { value: 'Household' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Rename' }));

    await waitFor(() => expect(screen.getByText('Household')).toBeTruthy());
    expect(screen.queryByText('Family')).toBeNull();
    expect(apiMock.patch).toHaveBeenCalledWith('/profiles/2', { name: 'Household' });
  });

  it('deletes a profile through the two-stage confirm (type DELETE)', async () => {
    apiMock.__seed([
      { id: 1, name: 'Default', has_password: false },
      { id: 2, name: 'Family', has_password: false },
    ]);
    await store.loadProfiles();

    render(Page);
    await waitFor(() => expect(screen.getByText('Family')).toBeTruthy());

    const familyRow = screen.getByText('Family').closest('.profile-manage-row');
    await fireEvent.click(within(familyRow).getByRole('button', { name: 'Delete' }));

    const confirmDialog = await screen.findByRole('dialog', { name: 'Delete Profile' });
    await fireEvent.click(within(confirmDialog).getByRole('button', { name: 'Delete' }));

    const typeInput = await screen.findByPlaceholderText('DELETE');
    const typeDialog = typeInput.closest('[role="dialog"]');
    await fireEvent.input(typeInput, { target: { value: 'DELETE' } });
    await fireEvent.click(within(typeDialog).getByRole('button', { name: 'Delete profile' }));

    await waitFor(() => expect(screen.queryByText('Family')).toBeNull());
    expect(apiMock.del).toHaveBeenCalledWith('/profiles/2');
  });
});
