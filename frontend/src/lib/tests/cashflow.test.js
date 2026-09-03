import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/cash-flow/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    cashFlow: vi.fn(),
    cashFlowTransactions: vi.fn(),
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

describe('cash-flow period rows', () => {
  beforeEach(() => {
    setLocale('en-US');
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders period labels in the selected locale', async () => {
    setLocale('es-ES');
    analyticsMock.cashFlow.mockResolvedValue({
      lines: [
        { period: '2025-01', type: 'INCOME', currency: 'EUR', total_value: 3500, count: 2, category: 'salary' },
        { period: '2025-01', type: 'MONEY_OUT', currency: 'EUR', total_value: 2800, count: 3, category: null },
      ],
      total_in: 3500,
      total_out: 2800,
      net: 700,
      rate_info: null,
    });
    render(Page);
    await waitFor(() => expect(screen.getByText('Entradas')).toBeTruthy());
    fireEvent.click(screen.getByText('Entradas'));
    await waitFor(() => expect(screen.getByText(/enero de 2025/i)).toBeTruthy());
  });
});

describe('cash-flow transaction detail table', () => {
  beforeEach(() => {
    setLocale('en-US');
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  function expandedState() {
    analyticsMock.cashFlow.mockResolvedValue({
      lines: [
        { period: '2025-01', type: 'INCOME', currency: 'USD', total_value: 1000, count: 1, category: 'salary' },
      ],
      total_in: 1000,
      total_out: 0,
      net: 1000,
      rate_info: null,
    });
    analyticsMock.cashFlowTransactions.mockResolvedValue({
      transactions: [
        {
          id: 1,
          date: '2025-01-15T10:00:00Z',
          description: 'January salary',
          source: 'Acme Corp',
          amount: 1000,
          currency: 'USD',
          rate: 0.75,
          display_amount: 750,
        },
      ],
      total_count: 1,
    });
    render(Page);
    return waitFor(() => expect(screen.getByText('Inflows')).toBeTruthy());
  }

  async function expandToTable() {
    await expandedState();
    fireEvent.click(screen.getByText('Inflows'));
    await waitFor(() => expect(screen.getByText('January 2025')).toBeTruthy());
    fireEvent.click(screen.getByText('January 2025'));
    await waitFor(() => expect(screen.getByText('Income')).toBeTruthy());
    fireEvent.click(screen.getByText('Income'));
    await waitFor(() => expect(screen.getByText('January salary')).toBeTruthy());
  }

  it('passes the display currency when loading transactions', async () => {
    await expandToTable();
    expect(analyticsMock.cashFlowTransactions).toHaveBeenCalledWith(
      expect.objectContaining({ displayCurrency: 'EUR' }),
    );
  });

  it('renders the native amount with its own currency symbol', async () => {
    await expandToTable();
    expect(screen.getByText('$1,000')).toBeTruthy();
  });

  it('renders the source of the money', async () => {
    await expandToTable();
    expect(screen.getByText('Acme Corp')).toBeTruthy();
  });

  it('renders the FX rate with the symbol pair prefix', async () => {
    await expandToTable();
    const rateCell = screen.getByText(/\$→€/).closest('td');
    expect(rateCell.textContent).toContain('0.7500');
  });

  it('renders the conversion to the display currency', async () => {
    await expandToTable();
    const conv = screen.getByText('€750');
    expect(conv).toBeTruthy();
  });

  it('falls back to a dash when no rate or display amount exists', async () => {
    analyticsMock.cashFlow.mockResolvedValue({
      lines: [
        { period: '2025-01', type: 'MONEY_OUT', currency: 'USD', total_value: 100, count: 1, category: null },
      ],
      total_in: 0,
      total_out: 100,
      net: -100,
      rate_info: null,
    });
    analyticsMock.cashFlowTransactions.mockResolvedValue({
      transactions: [{ id: 2, date: '2025-01-20T10:00:00Z', description: 'Rent', amount: 100, currency: 'USD' }],
      total_count: 1,
    });
    render(Page);
    await waitFor(() => expect(screen.getByText('Outflows')).toBeTruthy());
    fireEvent.click(screen.getByText('Outflows'));
    await waitFor(() => expect(screen.getByText('January 2025')).toBeTruthy());
    fireEvent.click(screen.getByText('January 2025'));
    await waitFor(() => expect(screen.getByText('Expenses')).toBeTruthy());
    fireEvent.click(screen.getByText('Expenses'));
    await waitFor(() => expect(screen.getByText('Rent')).toBeTruthy());
    const native = screen.getByText('$100');
    expect(native).toBeTruthy();
    const rateRow = native.closest('tr');
    expect(rateRow.textContent).toContain('—');
  });
});
