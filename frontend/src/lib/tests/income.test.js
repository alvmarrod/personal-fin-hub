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
