import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/dividends/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    dividends: vi.fn(),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    transactions: { getList: vi.fn(() => Promise.resolve([])) },
    portfolioAssets: { getList: vi.fn(() => Promise.resolve([])) },
    marketAssets: { getList: vi.fn(() => Promise.resolve([])) },
  },
}));

vi.mock('$lib/api/analytics.js', () => ({
  analytics: analyticsMock,
  crud: crudMock,
}));

const dividendsData = [
  { portfolio_asset_id: 1, market_code: 'AAPL.US', ticker: 'AAPL', currency: 'USD', total_dividends: 120.5, count: 4 },
  { portfolio_asset_id: 2, market_code: 'NVDA.US', ticker: 'NVDA', currency: 'USD', total_dividends: 45.0, count: 2 },
  { portfolio_asset_id: 3, market_code: 'VWCE.DE', ticker: null, currency: 'EUR', total_dividends: 210.75, count: 1 },
];

function rowTexts() {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map((r) => r.textContent);
}

describe('dividends by-asset table sorting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    analyticsMock.dividends.mockResolvedValue(dividendsData);
  });

  afterEach(cleanup);

  it('sorts by total dividends descending by default', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('VWCE.DE');
      expect(rows[1]).toContain('AAPL');
      expect(rows[2]).toContain('NVDA');
    });
  });

  it('sorts by total ascending on first click, descending on second', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.click(screen.getByText('Total'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
    fireEvent.click(screen.getByText('Total'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('VWCE.DE');
      expect(rows[2]).toContain('NVDA');
    });
  });

  it('sorts by asset ascending then descending', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.click(screen.getByText('Asset'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('AAPL');
      expect(rows[1]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
    fireEvent.click(screen.getByText('Asset'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('VWCE.DE');
      expect(rows[2]).toContain('AAPL');
    });
  });

  it('sorts by payments count descending on first click', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.click(screen.getByText('Payments'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('AAPL');
      expect(rows[1]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
  });
});
