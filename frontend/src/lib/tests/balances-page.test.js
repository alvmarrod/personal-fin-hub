import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/balance-snapshots/+page.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    balanceSnapshots: { getList: vi.fn(() => Promise.resolve([])) },
    entities: { getList: vi.fn(() => Promise.resolve([])) },
  },
}));

const { analyticsMock, currenciesMock } = vi.hoisted(() => ({
  analyticsMock: {
    cashBalances: vi.fn(() => Promise.resolve([])),
    cashByCurrencyHistory: vi.fn(() => Promise.resolve([])),
  },
  currenciesMock: { getList: vi.fn(() => Promise.resolve(['EUR', 'USD'])) },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));
vi.mock('$lib/api/analytics.js', () => ({
  crud: crudMock,
  analytics: analyticsMock,
  currenciesApi: currenciesMock,
}));

describe('Balances page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    crudMock.entities.getList.mockResolvedValue([{ id: 1, name: 'IBKR' }]);
    crudMock.balanceSnapshots.getList.mockResolvedValue([
      { id: 1, entity_id: 1, currency: 'USD', amount: 3274.89, timestamp: '2026-09-04T02:12:00', notes: 'JST' },
    ]);
    analyticsMock.cashBalances.mockResolvedValue([
      { entity_id: 1, currency: 'USD', balance: 10.89 },
      { entity_id: 1, currency: 'JPY', balance: 1344141.05 },
    ]);
    analyticsMock.cashByCurrencyHistory.mockResolvedValue([
      { date: '2026-09', currency: 'USD', balance: 10.89 },
      { date: '2026-10', currency: 'USD', balance: 10.89 },
    ]);
  });

  afterEach(cleanup);

  it('shows the derived current cash next to the latest snapshot', async () => {
    render(Page);

    await waitFor(() => expect(screen.getByText(/10\.89/)).toBeTruthy());
    expect(screen.getByText('Balances')).toBeTruthy();
    expect(screen.getAllByText(/3,275/).length).toBeGreaterThan(0);
    const days = Math.max(0, Math.floor((Date.now() - Date.parse('2026-09-04T02:12:00Z')) / 86_400_000));
    expect(screen.getByText(`${days}d`)).toBeTruthy();
    // A pocket without snapshots still gets a row.
    expect(screen.getByText('JPY')).toBeTruthy();
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(2);
  });

  it('shows an error with a retry when the cash history fails', async () => {
    analyticsMock.cashByCurrencyHistory.mockRejectedValueOnce(new Error('500'));
    const { container } = render(Page);

    await waitFor(() => expect(container.querySelectorAll('tr.group-row').length).toBe(2));
    const usdRow = [...container.querySelectorAll('tr.group-row')].find((row) =>
      row.textContent.includes('USD')
    );
    fireEvent.click(usdRow.querySelector('.expand-btn'));

    expect(await screen.findByText('Could not load the cash history.')).toBeTruthy();
    expect(screen.getByText('Retry')).toBeTruthy();
  });

  it('loads the cash history and the snapshots when a row expands', async () => {
    const { container } = render(Page);

    await waitFor(() => expect(container.querySelectorAll('tr.group-row').length).toBe(2));
    const usdRow = [...container.querySelectorAll('tr.group-row')].find((row) =>
      row.textContent.includes('USD')
    );
    fireEvent.click(usdRow.querySelector('.expand-btn'));

    await waitFor(() =>
      expect(analyticsMock.cashByCurrencyHistory).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(String),
        'month',
        1,
        'USD'
      )
    );
    expect((await screen.findAllByText('JST')).length).toBeGreaterThan(0);
  });
});
