import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/entities/+page.svelte';

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
    entities: {
      getList: vi.fn(() => Promise.resolve([])),
      getOne: vi.fn(() => Promise.resolve(null)),
      create: vi.fn(() => Promise.resolve({})),
      update: vi.fn(() => Promise.resolve({})),
      remove: vi.fn(() => Promise.resolve()),
      getDependents: vi.fn(() => Promise.resolve([])),
    },
  },
}));

const { analyticsMock, currenciesMock } = vi.hoisted(() => ({
  analyticsMock: {
    holdingsByEntity: vi.fn(() => Promise.resolve([])),
    historical: vi.fn(() => Promise.resolve([])),
  },
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve(['EUR', 'USD'])),
  },
}));

vi.mock('$lib/api/client.js', () => ({
  api: apiMock,
}));

vi.mock('$lib/api/analytics.js', () => ({
  crud: crudMock,
  analytics: analyticsMock,
  currenciesApi: currenciesMock,
}));

const entities = [
  { id: 1, name: 'Interactive Brokers', entity_type: 'BROKER', country: 'US' },
  { id: 2, name: 'Local Bank', entity_type: 'BANK', country: 'ES' },
];

const holdings = [
  { entity_id: 1, entity_name: 'Interactive Brokers', asset_class: 'STOCK', current_value: 9775, currency: 'USD' },
  { entity_id: 1, entity_name: 'Interactive Brokers', asset_class: 'ETF', current_value: 47376, currency: 'EUR' },
  { entity_id: 1, entity_name: 'Interactive Brokers', asset_class: 'CASH', current_value: 5000, currency: 'USD' },
  { entity_id: 2, entity_name: 'Local Bank', asset_class: 'CASH', current_value: 25497.32, currency: 'EUR' },
];

const hist = [
  { date: '2026-01-01', total_value: 100000, investment_value: 80000 },
  { date: '2026-02-01', total_value: 110000, investment_value: 85000 },
];

function mockApi() {
  apiMock.get.mockImplementation((path) => {
    if (path.startsWith('/entities')) return Promise.resolve(entities);
    if (path.startsWith('/currencies')) return Promise.resolve(['EUR', 'USD']);
    if (path.startsWith('/analytics/holdings-by-entity')) return Promise.resolve(holdings);
    if (path.startsWith('/analytics/historical')) return Promise.resolve(hist);
    return Promise.resolve([]);
  });
  crudMock.entities.getList.mockResolvedValue(entities);
  crudMock.entities.getDependents.mockResolvedValue({
    has_transactions: false,
    has_balance_snapshots: false,
    has_schedules: false,
  });
  analyticsMock.holdingsByEntity.mockResolvedValue(holdings);
  analyticsMock.historical.mockResolvedValue(hist);
  currenciesMock.getList.mockResolvedValue(['EUR', 'USD']);
}

beforeEach(() => {
  vi.clearAllMocks();
  setLocale('en-US');
  mockApi();
});

afterEach(cleanup);

describe('entities page', () => {
  it('renders one row per entity with B1 columns', async () => {
    render(Page);
    await screen.findByText('Interactive Brokers');
    await screen.findByText('Local Bank');
    const rowCells = screen.getAllByText('Interactive Brokers');
    expect(rowCells.length).toBe(1); // exactly one main row, no currency split
    expect(screen.getByText('Cash')).toBeTruthy();
    expect(screen.getByText('Others')).toBeTruthy();
    expect(screen.queryByText('Liquidity')).toBeNull();
    // no per-currency split in main rows
    expect(screen.queryByText('Interactive Brokers (USD)')).toBeNull();
    expect(screen.queryByText('Interactive Brokers (EUR)')).toBeNull();
  });

  it('re-fetches holdings with the selected currency', async () => {
    render(Page);
    await screen.findByText('Interactive Brokers');
    const select = screen.getByLabelText('Display currency');
    fireEvent.change(select, { target: { value: 'USD' } });
    await waitFor(() => {
      const calls = analyticsMock.holdingsByEntity.mock.calls.map(c => c[0]);
      expect(calls.some(c => c === 'USD')).toBe(true);
    });
  });

  it('renders per-currency nested rows under an expanded entity', async () => {
    render(Page);
    await screen.findByText('Interactive Brokers');
    const chevron = document.querySelector('.expand-btn');
    fireEvent.click(chevron);
    await screen.findByText(/Historical Value/);
    expect(screen.getAllByText('USD').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('EUR').length).toBeGreaterThanOrEqual(1);
  });

  it('toggles expansion off and clears the chart', async () => {
    render(Page);
    await screen.findByText('Interactive Brokers');
    const chevron = document.querySelector('.expand-btn');
    fireEvent.click(chevron);
    await screen.findByText(/Historical Value/);
    fireEvent.click(chevron);
    await waitFor(() => {
      expect(screen.queryByText(/Historical Value/)).toBeNull();
    });
  });

  it('highlights the selected row on click', async () => {
    const { container } = render(Page);
    await screen.findByText('Interactive Brokers');
    const row = container.querySelector('tbody tr');
    fireEvent.click(row);
    await waitFor(() => {
      expect(row.classList.contains('selected')).toBe(true);
    });
  });
});