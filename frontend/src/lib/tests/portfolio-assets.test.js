import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/portfolio-assets/+page.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    marketAssets: {
      getList: vi.fn(() => Promise.resolve([])),
    },
    portfolioAssets: {
      getList: vi.fn(() => Promise.resolve([])),
      getOne: vi.fn(() => Promise.resolve(null)),
      create: vi.fn(() => Promise.resolve({})),
      update: vi.fn(() => Promise.resolve({})),
      remove: vi.fn(() => Promise.resolve()),
      getManualValues: vi.fn(() => Promise.resolve([])),
      createManualValue: vi.fn(() => Promise.resolve({})),
      deleteManualValue: vi.fn(() => Promise.resolve()),
    },
  },
}));

vi.mock('$lib/api/client.js', () => ({
  api: apiMock,
}));

vi.mock('$lib/api/analytics.js', () => ({
  crud: crudMock,
}));

const fallbackAsset = {
  id: 1,
  market_code: 'VWCE.DE',
  is_active: true,
  net_quantity: 10,
  avg_cost: 100,
  latest_price: 110,
  price_source: 'transaction-fallback',
  price_as_of: '2025-03-10T09:00:00Z',
};

const noneAsset = {
  id: 2,
  market_code: 'NEW.US',
  is_active: true,
  net_quantity: 1,
  avg_cost: 50,
  latest_price: null,
  price_source: 'none',
  price_as_of: null,
};

const freshAsset = {
  id: 3,
  market_code: 'AAPL.US',
  is_active: true,
  net_quantity: 5,
  avg_cost: 150,
  latest_price: 200,
  price_source: 'market-api',
  price_as_of: '2025-06-01T12:00:00Z',
};

function mockAssets(assets) {
  apiMock.get.mockImplementation((path) => {
    if (path.startsWith('/portfolio-assets')) return Promise.resolve(assets);
    if (path.startsWith('/currencies')) return Promise.resolve(['USD']);
    if (path.startsWith('/prices/value-chart')) {
      return Promise.resolve({ data: {}, flagged_splits: [] });
    }
    return Promise.resolve([]);
  });
}

describe('portfolio-assets price warning callout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('shows stale price warning when assets use transaction fallback', async () => {
    mockAssets([fallbackAsset]);
    render(Page);
    const title = await screen.findByText('Prices from 3/10/2025 — market data unavailable');
    expect(title).toBeTruthy();
    expect(screen.getByText('Some assets are valued using their last known purchase price.')).toBeTruthy();
  });

  it('uses the oldest fallback date when multiple assets are stale', async () => {
    const older = { ...fallbackAsset, id: 4, market_code: 'OLD.US', price_as_of: '2024-11-20T08:00:00Z' };
    mockAssets([older, fallbackAsset]);
    render(Page);
    expect(await screen.findByText('Prices from 11/20/2024 — market data unavailable')).toBeTruthy();
  });

  it('shows no-price warning when an asset has no price data', async () => {
    mockAssets([noneAsset, freshAsset]);
    render(Page);
    expect(await screen.findByText('No price data for one or more holdings')).toBeTruthy();
    expect(screen.getByText("These assets have no market price yet. Click 'Sync Prices' to fetch market data.")).toBeTruthy();
  });

  it('renders no callout when all assets have fresh prices', async () => {
    mockAssets([freshAsset]);
    render(Page);
    await screen.findAllByText('AAPL.US');
    expect(screen.queryByText(/market data unavailable/)).toBeNull();
    expect(screen.queryByText(/No price data for one or more/)).toBeNull();
  });

  it('ignores inactive assets when computing the warning', async () => {
    mockAssets([{ ...noneAsset, is_active: false }]);
    render(Page);
    await screen.findAllByText('NEW.US');
    expect(screen.queryByText(/No price data for one or more/)).toBeNull();
  });
});

describe('portfolio-assets manual valuations', () => {
  const manualAsset = {
    id: 7,
    market_code: 'JP90C000ENA9',
    is_active: true,
    tracking_mode: 'manual',
    current_value_manual: 318601.0,
    price_source: 'manual',
    price_as_of: '2026-08-12T00:00:00Z',
  };

  async function clickRow(code) {
    const cells = await screen.findAllByText(code);
    fireEvent.click(cells[0].closest('tr'));
  }

  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('shows the valuations list when a manual asset row is clicked', async () => {
    mockAssets([manualAsset]);
    crudMock.portfolioAssets.getManualValues.mockResolvedValue([
      { id: 1, value: 300000, effective_date: '2026-01-01', notes: 'Jan revalue' },
      { id: 2, value: 318601, effective_date: '2026-07-01', notes: null },
    ]);
    render(Page);
    await clickRow('JP90C000ENA9');
    expect(await screen.findByText('Valuations')).toBeTruthy();
    expect(screen.getByText('2026-01-01')).toBeTruthy();
    expect(screen.getByText('2026-07-01')).toBeTruthy();
    expect(screen.getByText('Jan revalue')).toBeTruthy();
    expect(crudMock.portfolioAssets.getManualValues).toHaveBeenCalledWith(7);
  });

  it('does not show the valuations list for an auto-tracked asset', async () => {
    mockAssets([freshAsset]);
    render(Page);
    await clickRow('AAPL.US');
    expect(await screen.findByText(/Price History/)).toBeTruthy();
    expect(screen.queryByText('Valuations')).toBeNull();
  });

  it('creates a valuation through the modal', async () => {
    mockAssets([manualAsset]);
    crudMock.portfolioAssets.getManualValues.mockResolvedValue([]);
    render(Page);
    await clickRow('JP90C000ENA9');
    const addBtn = await screen.findByText('+ Add Valuation');
    fireEvent.click(addBtn);
    expect(await screen.findByText('Add Valuation')).toBeTruthy();
    fireEvent.input(document.querySelector('input[type="number"]'), { target: { value: '10000' } });
    fireEvent.input(document.querySelector('input[type="date"]'), { target: { value: '2026-08-01' } });
    fireEvent.click(screen.getByText('Save'));
    expect(crudMock.portfolioAssets.createManualValue).toHaveBeenCalledWith(7, {
      value: 10000,
      effective_date: '2026-08-01',
      notes: null,
    });
  });
});

describe('portfolio-assets table sorting', () => {
  const apple = { ...freshAsset, id: 1, market_code: 'AAPL.US', current_value: 1000, unrealized_pl_pct: 12 };
  const vanguard = { ...fallbackAsset, id: 2, market_code: 'VWCE.DE', current_value: 9000, unrealized_pl_pct: 45 };

  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    mockAssets([vanguard, apple]);
    crudMock.marketAssets.getList.mockResolvedValue([
      { market_code: 'AAPL.US', name: 'Apple', asset_type: 'STOCK', currency_code: 'USD' },
      { market_code: 'VWCE.DE', name: 'Vanguard', asset_type: 'FUND', currency_code: 'USD' },
    ]);
  });

  afterEach(cleanup);

  it('sorts by P&L % descending by default', async () => {
    render(Page);
    await screen.findAllByText('Apple');
    const rows = screen.getAllByRole('row');
    expect(rows[1].textContent).toContain('VWCE.DE');
    expect(rows[2].textContent).toContain('AAPL.US');
  });

  it('sorts by name ascending then descending', async () => {
    render(Page);
    await screen.findAllByText('Apple');
    fireEvent.click(screen.getByText('Name'));
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      expect(rows[1].textContent).toContain('Apple');
      expect(rows[2].textContent).toContain('Vanguard');
    });
    fireEvent.click(screen.getByText('Name'));
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      expect(rows[1].textContent).toContain('Vanguard');
      expect(rows[2].textContent).toContain('Apple');
    });
  });

  it('sorts by current value descending on first click', async () => {
    render(Page);
    await screen.findAllByText('Apple');
    fireEvent.click(screen.getByText('Current Value'));
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      expect(rows[1].textContent).toContain('VWCE.DE');
      expect(rows[2].textContent).toContain('AAPL.US');
    });
  });
});

describe('portfolio-assets P&L heat styling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    mockAssets([
      { ...freshAsset, id: 1, market_code: 'AAPL.US', is_active: true, unrealized_pl_pct: 25.5 },
      { ...fallbackAsset, id: 2, market_code: 'VWCE.DE', is_active: true, unrealized_pl_pct: -30.2 },
      { ...noneAsset, id: 3, market_code: 'NEW.US', is_active: true, unrealized_pl_pct: 0.4 },
    ]);
  });

  afterEach(cleanup);

  it('colors strong gains green and strong losses red, with arrows', async () => {
    const { container } = render(Page);
    await screen.findAllByText('AAPL.US');
    const hot = container.querySelector('.pl-hot');
    expect(hot).toBeTruthy();
    expect(hot.textContent).toContain('▲');
    expect(hot.textContent).toContain('25.50%');
    const bear = container.querySelector('.pl-bear');
    expect(bear).toBeTruthy();
    expect(bear.textContent).toContain('▼');
    expect(bear.textContent).toContain('-30.20%');
  });

  it('keeps near-zero P&L muted without an arrow', async () => {
    const { container } = render(Page);
    await screen.findAllByText('NEW.US');
    const flat = container.querySelector('.pl-flat');
    expect(flat).toBeTruthy();
    expect(flat.textContent).toContain('0.40%');
    expect(flat.textContent).not.toContain('▲');
    expect(flat.textContent).not.toContain('▼');
  });
});

describe('portfolio-assets asset type localization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    mockAssets([freshAsset]);
    crudMock.marketAssets.getList.mockResolvedValue([
      { market_code: 'AAPL.US', name: 'Apple', asset_type: 'STOCK', currency_code: 'USD' },
    ]);
  });

  afterEach(cleanup);

  it('translates the type column to the selected language', async () => {
    render(Page);
    await screen.findAllByText('Apple');
    expect(screen.getByText('Stock')).toBeTruthy();
    setLocale('es-ES');
    expect(await screen.findByText('Acción')).toBeTruthy();
    expect(screen.queryByText('Stock')).toBeNull();
  });
});
