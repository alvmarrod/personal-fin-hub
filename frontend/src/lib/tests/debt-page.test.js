import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/debt/+page.svelte';

const { debtMock } = vi.hoisted(() => ({
  debtMock: {
    list: vi.fn(),
    summary: vi.fn(),
    get: vi.fn(),
    counterparties: vi.fn(),
  },
}));

vi.mock('$lib/api/debt.js', () => ({ debtApi: debtMock }));

const { analyticsMock } = vi.hoisted(() => ({
  analyticsMock: {
    currencies: vi.fn(() => Promise.resolve(['EUR'])),
    entities: vi.fn(() => Promise.resolve([])),
  },
}));

vi.mock('$lib/api/analytics.js', () => ({
  currenciesApi: { getList: analyticsMock.currencies },
  crud: { entities: { getList: analyticsMock.entities } },
}));

const DEBT = {
  id: 1,
  direction: 'payable',
  counterparty_name: 'Bank',
  description: 'Mortgage',
  currency: 'EUR',
  principal: 10000,
  start_date: '2026-01-01',
  term_months: 12,
  maturity_date: '2027-01-01',
  installment_mode: 'equal_payment',
  installment_amount: 900,
  principal_per_installment: null,
  day_count: 'monthly',
  rate_reset_mode: 'recalculate_installment',
  review_period_months: 12,
  disbursement_mode: 'none',
  disbursement_entity_id: null,
  disbursement_date: null,
  status: 'active',
  settled_at: null,
  settled_amount: null,
  settlement_adjustment: null,
  notes: null,
  current_rate: 12,
  outstanding_principal: 9000,
  accrued_interest: 90,
  total_due: 9090,
  progress_pct: 10,
  next_payment_date: '2026-02-01',
  next_payment_amount: 900,
};

const SUMMARY = {
  display_currency: 'EUR',
  payable: 9000,
  receivable: 0,
  payable_count: 1,
  receivable_count: 0,
  payable_accrued_interest: 90,
  receivable_accrued_interest: 0,
  next_payable: null,
  next_receivable: null,
};

describe('Debt page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    debtMock.list.mockResolvedValue([DEBT]);
    debtMock.summary.mockResolvedValue(SUMMARY);
    debtMock.get.mockResolvedValue({ ...DEBT, rates: [], payments: [], plan: [] });
    debtMock.counterparties.mockResolvedValue(['Bank']);
  });

  afterEach(cleanup);

  it('renders the summary and the active debt', async () => {
    render(Page);

    await screen.findByText('Bank');
    expect(screen.getByText('Debt I owe')).toBeTruthy();
    expect(screen.getAllByText('Owed to me').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0);
    expect(debtMock.summary).toHaveBeenCalled();
  });

  it('reloads with a direction filter', async () => {
    render(Page);
    await screen.findByText('Bank');

    await fireEvent.click(screen.getByRole('button', { name: 'I owe' }));

    await waitFor(() =>
      expect(debtMock.list).toHaveBeenLastCalledWith(expect.objectContaining({ direction: 'payable' })),
    );
  });

  it('opens the detail modal for a row', async () => {
    render(Page);
    await fireEvent.click(await screen.findByText('Bank'));

    await waitFor(() => expect(debtMock.get).toHaveBeenCalledWith(1));
  });
});
