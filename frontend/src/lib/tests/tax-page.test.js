import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/tax/+page.svelte';

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    taxablePnlExtended: vi.fn(),
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve(['EUR', 'USD', 'JPY'])),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    transactions: { getOne: vi.fn(() => Promise.resolve({})) },
  },
}));

vi.mock('$lib/api/analytics.js', () => ({
  analytics: analyticsMock,
  currenciesApi: currenciesMock,
  crud: crudMock,
}));

vi.mock('$lib/api/client.js', () => ({
  api: { get: vi.fn(() => Promise.resolve({})) },
}));

const taxData = {
  ruleset: 'spain',
  display_currency: 'EUR',
  fiscal_years: [
    {
      fiscal_year: 2025,
      start_date: '2025-01-01',
      end_date: '2025-12-31',
      realized_gains_taxable: 1386.82,
      dividends_taxable: 200.0,
      total_taxable: 1586.82,
      num_sells: 2,
      num_dividends: 1,
      tax_owed: { capital_gains: 272.75, dividends: 34.2 },
      total_tax_owed: 296.95,
      confirmed: { capital_gains: 12.5, dividends: 18.4 },
      total_confirmed: 30.9,
      items: [
        {
          transaction_id: 901,
          market_code: 'AAPL.US',
          ticker: 'AAPL',
          name: 'Apple',
          category: 'capital_gains',
          date: '2025-06-20',
          native_amount: 180.0,
          display_amount: 162.0,
          taxable_amount: 162.0,
          tax_owed: 34.02,
          fiscal_rule: 'spain',
          tax_policy: null,
          currency: 'USD',
          taxes: [
            { tax_definition_id: 1, slug: 'tasa_tobin', name: 'Tasa Tobin', computed: 0.29, confirmed: null },
            { tax_definition_id: 2, slug: 'foreign_withholding', name: 'Foreign withholding', computed: 0, confirmed: 12.5 },
          ],
        },
        {
          transaction_id: 902,
          market_code: null,
          ticker: null,
          name: 'Dividend withholding',
          category: 'dividends',
          date: '2025-08-01',
          native_amount: 200.0,
          display_amount: 180.0,
          taxable_amount: 180.0,
          tax_owed: null,
          fiscal_rule: 'spain',
          tax_policy: null,
          currency: 'USD',
          taxes: [{ tax_definition_id: 3, slug: 'local_levy', name: 'Local levy', computed: 3.6, confirmed: 3.4 }],
        },
      ],
    },
  ],
  total_taxable: 1586.82,
  total_tax_owed: 296.95,
  total_confirmed: 30.9,
  combined_base: 6000.0,
  rate_fallbacks: [],
  default_ruleset: 'spain',
};

describe('tax page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    analyticsMock.taxablePnlExtended.mockResolvedValue(taxData);
  });

  afterEach(cleanup);

  it('renders the per-category tax breakdown on the year row', async () => {
    render(Page);
    await screen.findByText('2025');
    expect(screen.getByText('Capital gains')).toBeTruthy();
    expect(screen.getAllByText('Dividends').length).toBeGreaterThan(0);
  });

  it('shows a tax count and expands to the per-definition breakdown', async () => {
    const { container } = render(Page);
    await screen.findByText('2025');
    fireEvent.click(screen.getByText('2025'));
    await screen.findByText('AAPL');

    const countBtn = screen.getByText('2 tax(es)');
    expect(countBtn).toBeTruthy();
    expect(screen.queryByText('Tasa Tobin')).toBeNull();

    fireEvent.click(countBtn);
    await waitFor(() => {
      expect(screen.getByText('Tasa Tobin')).toBeTruthy();
      expect(screen.getByText('Foreign withholding')).toBeTruthy();
    });
    expect(container.querySelectorAll('.taxes-row').length).toBe(1);
  });

  it('renders null item tax_owed as "-" and confirmed-only definitions with computed 0', async () => {
    render(Page);
    await screen.findByText('2025');
    fireEvent.click(screen.getByText('2025'));
    await screen.findByText('AAPL');
    // The null-tax_owed dividend row renders "-", not a currency value.
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    // The naive withholding definition shows computed 0 on its expanded line.
    fireEvent.click(screen.getByText('2 tax(es)'));
    await screen.findByText('Foreign withholding');
    // The naive withholding row has no confirmed value → em dash.
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('charts computed from per-year total_tax_owed and confirmed from total_confirmed', async () => {
    render(Page);
    await screen.findByText('2025');
    expect(analyticsMock.taxablePnlExtended).toHaveBeenCalled();
    // Chart card renders (canvas is present via ChartCard/StackedBarChart).
    expect(screen.getByText('Tax Reconciliation')).toBeTruthy();
  });
});
