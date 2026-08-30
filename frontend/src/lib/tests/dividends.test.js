import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/dividends/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    dividends: vi.fn(),
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve(['USD', 'EUR'])),
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
  currenciesApi: currenciesMock,
  crud: crudMock,
}));

const dividendsData = [
  { portfolio_asset_id: 1, market_code: 'AAPL.US', ticker: 'AAPL', currency: 'USD', total_dividends: 120.5, count: 4, total_dividends_display: 60.0 },
  { portfolio_asset_id: 2, market_code: 'NVDA.US', ticker: 'NVDA', currency: 'USD', total_dividends: 45.0, count: 2, total_dividends_display: 22.5 },
  { portfolio_asset_id: 3, market_code: 'VWCE.DE', ticker: null, currency: 'EUR', total_dividends: 210.75, count: 1, total_dividends_display: 105.5 },
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

  it('sorts by amount ascending on first click, descending on second', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.click(screen.getByText('Amount'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
    fireEvent.click(screen.getByText('Amount'));
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

  it('sorts by original amount descending on first click, ascending on second', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.click(screen.getByText('Original Amount'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('VWCE.DE');
      expect(rows[1]).toContain('AAPL');
      expect(rows[2]).toContain('NVDA');
    });
    fireEvent.click(screen.getByText('Original Amount'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
  });

  it('shows native original amount and converted amount cells', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    expect(screen.getByText('$120.5')).toBeTruthy();
    expect(screen.getByText('€210.75')).toBeTruthy();
    expect(screen.getByText('€105.5')).toBeTruthy();
  });

  it('shows the total dividends card converted to the display currency', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    await waitFor(() => {
      expect(screen.getByText('€188.00')).toBeTruthy();
    });
  });

  it('renders the currency selector', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    expect(screen.getByRole('combobox')).toBeTruthy();
  });

  it('refetches dividends with the new display currency on change', async () => {
    render(Page);
    await screen.findAllByText('VWCE.DE');
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'USD' } });
    await waitFor(() => {
      expect(analyticsMock.dividends).toHaveBeenLastCalledWith({ displayCurrency: 'USD' });
    });
  });
});

describe('dividends transaction table amount formatting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('es-ES');
    analyticsMock.dividends.mockResolvedValue([]);
    crudMock.transactions.getList.mockResolvedValue([
      { id: 1, timestamp: '2026-01-10T00:00:00Z', portfolio_asset_id: 9, income_category: 'dividends', total_value: 9802, currency: 'JPY', dividend_type: null, notes: null },
      { id: 2, timestamp: '2026-01-11T00:00:00Z', portfolio_asset_id: 9, income_category: 'dividends', total_value: 678841, currency: 'JPY', dividend_type: null, notes: null },
    ]);
  });

  afterEach(cleanup);

  it('renders grouped JPY amounts (thousands dot) for every magnitude', async () => {
    render(Page);
    await screen.findAllByText('9.802');
    expect(screen.getByText('678.841')).toBeTruthy();
  });
});
