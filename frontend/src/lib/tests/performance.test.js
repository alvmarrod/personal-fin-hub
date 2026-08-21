import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/performance/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    performance: vi.fn(),
    realizedGains: vi.fn(),
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve([])),
  },
}));

vi.mock('$lib/api/analytics.js', () => ({
  analytics: analyticsMock,
  currenciesApi: currenciesMock,
}));

const performanceData = {
  display_currency: 'USD',
  total_portfolio_value: 1000,
  total_invested_now: 900,
  total_invested_historic: 1200,
  total_return_pct: 5,
  total_unrealized_pl: 30,
  unrealized_pl_pct: 3.33,
  total_realized_pl: 30,
  realized_pl_pct: 2.5,
  total_dividends: 150,
  dividend_yield_pct: 12.5,
  total_interest: 25,
  total_return: 210,
  rule_key: 'default',
  rate_fallbacks: [],
};

const gains = [
  {
    transaction_id: 1,
    ticker: 'AAPL',
    market_code: 'AAPL.US',
    sell_date: '2025-06-20T00:00:00',
    sell_quantity: 20,
    sell_price: 198.5,
    sell_total: 3970.0,
    cost_basis: 3504.0,
    realized_pl: 466.0,
    realized_pl_pct: 13.3,
    currency: 'USD',
  },
  {
    transaction_id: 2,
    ticker: 'NVDA',
    market_code: 'NVDA.US',
    sell_date: '2025-05-10T00:00:00',
    sell_quantity: 10,
    sell_price: 520.0,
    sell_total: 5200.0,
    cost_basis: 4500.0,
    realized_pl: 700.0,
    realized_pl_pct: 15.56,
    currency: 'USD',
  },
  {
    transaction_id: 3,
    ticker: null,
    market_code: 'VWCE.DE',
    sell_date: '2025-04-02T00:00:00',
    sell_quantity: 50,
    sell_price: 108.64,
    sell_total: 5431.82,
    cost_basis: 4925.0,
    realized_pl: -450.0,
    realized_pl_pct: -12.0,
    currency: 'EUR',
  },
];

function rowTexts() {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map((r) => r.textContent);
}

describe('performance realized gains table sorting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    analyticsMock.performance.mockResolvedValue(performanceData);
    analyticsMock.realizedGains.mockResolvedValue(gains);
  });

  afterEach(cleanup);

  it('sorts by sell date descending by default', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('AAPL');
      expect(rows[1]).toContain('NVDA');
      expect(rows[2]).toContain('VWCE.DE');
    });
  });

  it('sorts by P&L % descending on first click then ascending on second', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
    fireEvent.click(screen.getByText('P&L %'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('NVDA');
      expect(rows[1]).toContain('AAPL');
      expect(rows[2]).toContain('VWCE.DE');
    });
    fireEvent.click(screen.getByText('P&L %'));
    await waitFor(() => {
      const rows = rowTexts();
      expect(rows[0]).toContain('VWCE.DE');
      expect(rows[1]).toContain('AAPL');
      expect(rows[2]).toContain('NVDA');
    });
  });

  it('sorts by asset ascending then descending', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
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
      expect(rows[1]).toContain('NVDA');
      expect(rows[2]).toContain('AAPL');
    });
  });
});

describe('performance income and group layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    analyticsMock.performance.mockResolvedValue(performanceData);
    analyticsMock.realizedGains.mockResolvedValue(gains);
  });

  afterEach(cleanup);

  it('renders dividends card with yield sub-line', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
    expect(screen.getByText('Dividends')).toBeTruthy();
    expect(screen.getByText('€150.00')).toBeTruthy();
    expect(screen.getByText('12.50% all-time')).toBeTruthy();
  });

  it('renders interest card', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
    expect(screen.getByText('Interest')).toBeTruthy();
    expect(screen.getByText('€25.00')).toBeTruthy();
  });

  it('renders metric groups with labels', async () => {
    const { container } = render(Page);
    await screen.findAllByText('AAPL');
    for (const label of ['Portfolio', 'Unrealized', 'Realized · Trading', 'Investment Income', 'Total']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(container.querySelectorAll('.metric-group').length).toBe(5);
    expect(container.querySelector('.metric-group .metric-card.compact')).toBeTruthy();
  });

  it('places Total beside Portfolio in the first row', async () => {
    const { container } = render(Page);
    await screen.findAllByText('AAPL');
    const topRow = container.querySelector('.top-row');
    expect(topRow).toBeTruthy();
    const tabs = [...topRow.querySelectorAll('.group-tab')].map((el) => el.textContent);
    expect(tabs[0]).toBe('Portfolio');
    expect(tabs[1]).toBe('Total');
    expect(container.querySelectorAll('.top-row .metric-group').length).toBe(2);
  });

  it('shows no rate warning without fallbacks', async () => {
    const { container } = render(Page);
    await screen.findAllByText('AAPL');
    expect(container.querySelector('.rate-warning-inline')).toBeNull();
  });

  it('renders inline rate warning in the header when fallbacks are present', async () => {
    analyticsMock.performance.mockResolvedValue({
      ...performanceData,
      rate_fallbacks: [{ currency: 'USD', scope: 'dividends', reason: 'closest-in-time', count: 2 }],
    });
    const { container } = render(Page);
    await screen.findAllByText('AAPL');
    const warning = container.querySelector('.page-header .rate-warning-inline');
    expect(warning).toBeTruthy();
    expect(warning.textContent).toContain('Some values use the closest available rate');
    expect(warning.textContent).toContain('Historical exchange rates are missing');
  });

  it('labels realized cards as trading-only', async () => {
    render(Page);
    await screen.findAllByText('AAPL');
    expect(screen.getAllByText('Realized P&L % (Trading)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Realized P&L (Trading)').length).toBeGreaterThan(0);
  });
});
