import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn() },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));

let store;

async function freshStore() {
  vi.resetModules();
  store = await import('./updates.svelte.ts');
}

describe('updates store', () => {
  beforeEach(async () => {
    vi.useFakeTimers();
    await freshStore();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('exposes backend and frontend status after polling', async () => {
    apiMock.get.mockResolvedValue({
      enabled: true,
      backend: { current: '0.11.0', latest: '0.12.0', outdated: true, url: 'https://example.com/r' },
      frontend: { current: '0.9.0', latest: '0.9.0', outdated: false, url: null },
    });

    await store.initUpdatePolling();

    expect(apiMock.get).toHaveBeenCalledTimes(1);
    expect(apiMock.get.mock.calls[0][0]).toMatch(/^\/updates\?frontend_version=/);
    expect(store.backendUpdate().outdated).toBe(true);
    expect(store.backendUpdate().latest).toBe('0.12.0');
    expect(store.frontendUpdate().outdated).toBe(false);
  });

  it('clears state when the check is disabled', async () => {
    apiMock.get.mockResolvedValue({ enabled: false });
    await store.initUpdatePolling();
    expect(store.backendUpdate()).toBeNull();
    expect(store.frontendUpdate()).toBeNull();
  });

  it('clears state on failure (fail-open)', async () => {
    apiMock.get.mockRejectedValue(new Error('network'));
    await store.initUpdatePolling();
    expect(store.backendUpdate()).toBeNull();
    expect(store.frontendUpdate()).toBeNull();
  });

  it('dismissUpdate hides the statuses', async () => {
    apiMock.get.mockResolvedValue({
      enabled: true,
      backend: { current: '0.11.0', latest: '0.12.0', outdated: true, url: 'u' },
      frontend: null,
    });
    await store.initUpdatePolling();
    expect(store.backendUpdate().outdated).toBe(true);

    store.dismissUpdate();
    expect(store.backendUpdate()).toBeNull();
    expect(store.frontendUpdate()).toBeNull();
  });

  it('polls only once per init', async () => {
    apiMock.get.mockResolvedValue({ enabled: false });
    await store.initUpdatePolling();
    await store.initUpdatePolling();
    expect(apiMock.get).toHaveBeenCalledTimes(1);
  });
});
