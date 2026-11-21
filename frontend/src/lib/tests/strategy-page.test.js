import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { privacyHidden, togglePrivacy } from '$lib/preferences/privacy.svelte';
import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
import Page from '../../routes/strategy/+page.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn(), postFile: vi.fn() },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock, setMockStore: vi.fn() }));

const SETS = [
  {
    effective_from: '2026-01-01',
    targets: { equities: 55, bonds: 30, cash: 15, real_estate: 0, gold: 0 },
    updated_at: '2026-01-01 10:00:00',
  },
  {
    effective_from: '2027-01-01',
    targets: { equities: 53, bonds: 32, cash: 15, real_estate: 0, gold: 0 },
    updated_at: '2026-11-01 10:00:00',
  },
];

const DRIFT = {
  effective_from: '2026-01-01',
  as_of: '2026-11-21',
  total: 30700,
  rate_missing: false,
  buckets: [
    { bucket: 'equities', target_pct: 55, value: 19034, share_pct: 62.0, drift_pp: 7.0, amount_to_move: -2149, rate_missing: false },
    { bucket: 'bonds', target_pct: 30, value: 7368, share_pct: 24.0, drift_pp: -6.0, amount_to_move: 1842, rate_missing: false },
    { bucket: 'cash', target_pct: 15, value: 3070, share_pct: 10.0, drift_pp: -5.0, amount_to_move: 1535, rate_missing: false },
    { bucket: 'real_estate', target_pct: 0, value: 0, share_pct: 0.0, drift_pp: 0.0, amount_to_move: 0, rate_missing: false },
    { bucket: 'gold', target_pct: 0, value: 0, share_pct: 0.0, drift_pp: 0.0, amount_to_move: 0, rate_missing: false },
  ],
  unassigned: { value: 1228, share_pct: 4.0, rate_missing: false },
};

const HISTORY = {
  points: [
    { date: '2026-01-01', bucket: 'equities', value: 15000, share_pct: 50.0, target_pct: 55.0 },
    { date: '2026-06-01', bucket: 'equities', value: 19034, share_pct: 62.0, target_pct: 55.0 },
    { date: '2026-01-01', bucket: 'bonds', value: 9000, share_pct: 30.0, target_pct: 30.0 },
    { date: '2026-06-01', bucket: 'bonds', value: 7368, share_pct: 24.0, target_pct: 30.0 },
    { date: '2026-06-01', bucket: 'unassigned', value: 1228, share_pct: 4.0, target_pct: null },
  ],
};

function mockData(sets = SETS, drift = DRIFT, history = HISTORY) {
  apiMock.get.mockImplementation((path) => {
    if (path === '/strategy') return Promise.resolve(sets);
    if (path.startsWith('/strategy/drift')) return Promise.resolve(drift);
    if (path.startsWith('/strategy/history')) return Promise.resolve(history);
    return Promise.resolve(null);
  });
}

describe('Strategy page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    tutorialStore.abandon();
    setLocale('en-US');
    if (privacyHidden()) togglePrivacy();
    mockData();
    apiMock.post.mockResolvedValue({});
    apiMock.put.mockResolvedValue({});
    apiMock.del.mockResolvedValue(null);
  });

  afterEach(() => {
    cleanup();
    if (privacyHidden()) togglePrivacy();
  });

  it('renders the timeline with current and planned sets', async () => {
    render(Page);
    await screen.findByText('Target sets');

    expect(screen.getByText('Current')).toBeTruthy();
    expect(screen.getByText('Planned')).toBeTruthy();
    expect(screen.getAllByText(/Renta|Equities/).length).toBeGreaterThan(0);
  });

  it('renders drift with targets, shares and percentage points', async () => {
    render(Page);
    await screen.findByText(/Current drift/);

    expect(screen.getByText('+7.0 pp')).toBeTruthy();
    expect(screen.getByText('-6.0 pp')).toBeTruthy();
    expect(screen.getByText('Unassigned')).toBeTruthy();
    expect(screen.getByText('4.0%')).toBeTruthy();
  });

  it('highlights rows beyond five percentage points', async () => {
    const { container } = render(Page);
    await screen.findByText(/Current drift/);

    const banded = container.querySelectorAll('tbody tr.band');
    expect(banded.length).toBe(2);
  });

  it('shows the empty state without sets', async () => {
    mockData([], { ...DRIFT, effective_from: null, buckets: [] });
    render(Page);
    await screen.findByText('No target allocation yet');
  });

  it('starts the tutorial from the replay button with no sets', async () => {
    mockData([], { ...DRIFT, effective_from: null, buckets: [] });
    const { container } = render(Page);
    await screen.findByText('No target allocation yet');

    await fireEvent.click(container.querySelector('.replay-btn'));

    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeTruthy(), {
      timeout: 4000,
    });
  });

  it('shows the no-target state when no set has started', async () => {
    mockData([SETS[1]], { ...DRIFT, effective_from: null, buckets: [] });
    render(Page);
    await screen.findByText('No target defined for today');
    expect(screen.getByText(/first set starts/)).toBeTruthy();
  });

  it('renders the historical comparison with its caveat', async () => {
    render(Page);
    await screen.findByText('Historical comparison');

    expect(screen.getByText('Solid: actual · Dashed: target')).toBeTruthy();
    expect(screen.getByText(/latest FX rate/)).toBeTruthy();
    expect(screen.getByText('Unassigned today: 4.0%')).toBeTruthy();
  });

  it('reloads the history with a weekly interval for 3M', async () => {
    render(Page);
    await screen.findByText('Historical comparison');

    await fireEvent.click(screen.getByText('3M'));

    await waitFor(() =>
      expect(apiMock.get).toHaveBeenCalledWith(expect.stringContaining('interval=week')),
    );
  });

  it('gates Save on a total of 100 and posts the set', async () => {
    const { container } = render(Page);
    await screen.findByText('Target sets');

    await fireEvent.click(screen.getByText('+ Add target set'));

    const save = screen.getByText('Save');
    expect(save.disabled).toBe(true);

    const inputs = container.querySelectorAll('.strategy-form input[type="number"]');
    await fireEvent.input(inputs[0], { target: { value: '100' } });
    await waitFor(() => expect(save.disabled).toBe(false));

    await fireEvent.click(save);

    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith('/strategy', {
        effective_from: '2026-11-21',
        targets: { equities: 100, bonds: 0, cash: 0, real_estate: 0, gold: 0 },
      }),
    );
  });

  it('masks amounts but keeps shares in privacy mode', async () => {
    togglePrivacy();
    render(Page);
    await screen.findByText(/Current drift/);

    expect(screen.getAllByText(/\*\*\*\*\*\*\*\*/).length).toBeGreaterThan(0);
    expect(screen.getByText('62%')).toBeTruthy();
  });

  it('deletes a set after confirmation', async () => {
    render(Page);
    await screen.findByText('Target sets');

    await fireEvent.click(screen.getAllByText('Delete')[0]);
    const buttons = screen.getAllByText('Delete');
    await fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => expect(apiMock.del).toHaveBeenCalledWith('/strategy/2026-01-01'));
  });
});
