import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/income/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    cashFlow: vi.fn(),
    incomeBySource: vi.fn(),
    projectedIncome: vi.fn(),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    transactions: { getList: vi.fn(() => Promise.resolve([])) },
    entities: { getList: vi.fn(() => Promise.resolve([])) },
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve([])),
  },
}));

vi.mock('$lib/api/analytics.js', () => ({
  analytics: analyticsMock,
  crud: crudMock,
  currenciesApi: currenciesMock,
}));

function withRateInfo(rateInfo) {
  return { data: [], rate_info: rateInfo };
}

describe('income rate staleness banner', () => {
  beforeEach(() => {
    setLocale('en-US');
    analyticsMock.cashFlow.mockResolvedValue({ lines: [], rate_info: null });
    analyticsMock.incomeBySource.mockResolvedValue(withRateInfo(null));
    analyticsMock.projectedIncome.mockResolvedValue(withRateInfo(null));
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('hides the banner when rates are fresh', async () => {
    analyticsMock.incomeBySource.mockImplementation(({ displayCurrency } = {}) =>
      Promise.resolve(withRateInfo(displayCurrency ? { rates: { USD: 1.08 }, latest_timestamp: '2026-08-22T00:00:00Z', stale: false } : null)),
    );
    render(Page);
    await waitFor(() => expect(analyticsMock.incomeBySource).toHaveBeenCalled());
    expect(screen.queryByText(/Exchange rates from/)).toBeNull();
  });

  it('shows the banner when rates are stale', async () => {
    analyticsMock.projectedIncome.mockImplementation(({ displayCurrency } = {}) =>
      Promise.resolve(withRateInfo(displayCurrency ? { rates: { USD: 1.08 }, latest_timestamp: '2026-08-12T00:00:00Z', stale: true } : null)),
    );
    render(Page);
    await waitFor(() => expect(screen.getByText(/Exchange rates from/)).toBeTruthy());
  });

  it('hides the banner when no source provides rate info', async () => {
    render(Page);
    await waitFor(() => expect(analyticsMock.incomeBySource).toHaveBeenCalled());
    expect(screen.queryByText(/Exchange rates from/)).toBeNull();
  });
});

describe('income tables amount formatting', () => {
  beforeEach(() => {
    setLocale('es-ES');
    analyticsMock.cashFlow.mockResolvedValue({ lines: [], rate_info: null });
    analyticsMock.incomeBySource.mockImplementation(({ displayCurrency } = {}) =>
      displayCurrency
        ? Promise.resolve({ data: [], rate_info: null })
        : Promise.resolve({ data: [{ entity_name: 'Employer', entity_id: 1, currency: 'JPY', income_category: 'salary', period: '2026-08', total_value: 9802 }], rate_info: null }),
    );
    analyticsMock.projectedIncome.mockImplementation(({ displayCurrency } = {}) =>
      displayCurrency
        ? Promise.resolve({ data: [], rate_info: null })
        : Promise.resolve({ data: [], rate_info: null }),
    );
    crudMock.transactions.getList.mockResolvedValue([
      { id: 1, timestamp: '2026-08-10T00:00:00Z', type: 'INCOME', entity_id: 1, income_category: 'other', total_value: 8340, currency: 'JPY', notes: null },
      { id: 2, timestamp: '2026-08-11T00:00:00Z', type: 'INCOME', entity_id: 1, income_category: 'dividends', total_value: 678841, currency: 'JPY', notes: null },
    ]);
    crudMock.entities.getList.mockResolvedValue([{ id: 1, name: 'Employer', entity_type: 'OTHER' }]);
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders grouped JPY amounts in every table under es-ES', async () => {
    render(Page);
    await waitFor(() => expect(screen.getAllByText('9.802 JPY').length).toBeGreaterThan(0));
    expect(screen.getByText('8.340')).toBeTruthy();
    expect(screen.getByText('678.841')).toBeTruthy();
  });
});
