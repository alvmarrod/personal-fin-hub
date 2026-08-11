import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
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
