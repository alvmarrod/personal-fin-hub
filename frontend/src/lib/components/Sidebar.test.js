import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { APP_VERSION } from '$lib/version.js';
import Sidebar from './Sidebar.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn() },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));

describe('Sidebar versions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('shows the frontend version and the version reported by the backend', async () => {
    apiMock.get.mockResolvedValue({ version: '9.9.9' });
    render(Sidebar, { props: { open: true } });

    expect(await screen.findByText(`Frontend: ${APP_VERSION}`)).toBeTruthy();
    expect(await screen.findByText('Backend: 9.9.9')).toBeTruthy();
    expect(apiMock.get).toHaveBeenCalledWith('/version');
  });

  it('shows a dash when the backend version cannot be read', async () => {
    apiMock.get.mockRejectedValue(new Error('offline'));
    render(Sidebar, { props: { open: true } });

    expect(await screen.findByText('Backend: —')).toBeTruthy();
  });
});
