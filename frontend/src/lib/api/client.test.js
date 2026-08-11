import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, setActiveProfileId } from './client.js';

describe('api client profile header', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      })
    );
    setActiveProfileId(null);
  });

  afterEach(() => {
    setActiveProfileId(null);
    vi.restoreAllMocks();
  });

  it('throws when no profile is active for a profile-scoped endpoint', async () => {
    await expect(api.get('/entities')).rejects.toThrow('No active profile');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('allows public endpoints without a profile', async () => {
    await api.get('/profiles');
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/profiles');
  });

  it('attaches X-Profile-ID when a profile is active', async () => {
    setActiveProfileId(42);
    await api.get('/entities');
    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['X-Profile-ID']).toBe('42');
  });

  it('updates the header when the active profile changes', async () => {
    setActiveProfileId(1);
    await api.get('/entities');
    let [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['X-Profile-ID']).toBe('1');

    setActiveProfileId(7);
    await api.get('/entities');
    [, opts] = globalThis.fetch.mock.calls[1];
    expect(opts.headers['X-Profile-ID']).toBe('7');
  });

  it('throws after clearing the active profile', async () => {
    setActiveProfileId(42);
    await api.get('/entities');
    setActiveProfileId(null);
    await expect(api.get('/entities')).rejects.toThrow('No active profile');
  });

  it('includes Content-Type on every request', async () => {
    setActiveProfileId(1);
    await api.post('/entities', { name: 'X' });
    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(opts.headers['X-Profile-ID']).toBe('1');
  });

  it('sends a PATCH request with JSON body', async () => {
    setActiveProfileId(1);
    await api.patch('/profiles/1', { name: 'Renamed' });
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/profiles/1');
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({ name: 'Renamed' });
    expect(opts.headers['X-Profile-ID']).toBe('1');
  });
});
