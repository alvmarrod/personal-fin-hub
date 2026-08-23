import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/cash-flow/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    cashFlow: vi.fn(),
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

function cashFlowPayload(rateInfo) {
  return {
    lines: [],
    total_in: 0,
    total_out: 0,
    net: 0,
    rate_info: rateInfo,
  };
}

describe('cash-flow rate staleness banner', () => {
  beforeEach(() => {
    setLocale('en-US');
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('hides the banner when rates are fresh', async () => {
    analyticsMock.cashFlow.mockResolvedValue(
      cashFlowPayload({ rates: { USD: 1.08 }, latest_timestamp: '2026-08-22T00:00:00Z', stale: false }),
    );
    render(Page);
    await waitFor(() => expect(analyticsMock.cashFlow).toHaveBeenCalled());
    expect(screen.queryByText(/Exchange rates from/)).toBeNull();
  });

  it('shows the banner when rates are stale', async () => {
    analyticsMock.cashFlow.mockResolvedValue(
      cashFlowPayload({ rates: { USD: 1.08 }, latest_timestamp: '2026-08-12T00:00:00Z', stale: true }),
    );
    render(Page);
    await waitFor(() => expect(screen.getByText(/Exchange rates from/)).toBeTruthy());
  });

  it('hides the banner when there is no rate info', async () => {
    analyticsMock.cashFlow.mockResolvedValue(cashFlowPayload(null));
    render(Page);
    await waitFor(() => expect(analyticsMock.cashFlow).toHaveBeenCalled());
    expect(screen.queryByText(/Exchange rates from/)).toBeNull();
  });
});
