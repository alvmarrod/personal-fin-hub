import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import DetailTransactionModal from '../components/modals/DetailTransactionModal.svelte';

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn() } }));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));

function buy(overrides = {}) {
  return {
    id: 1,
    timestamp: '2026-11-12T00:00:00',
    type: 'INVESTMENT_BUY',
    entity_id: 3,
    currency: 'USD',
    total_value: 3264,
    quantity: 1,
    unit_price: 3264,
    cash_handling: null,
    cash_handling_effective: 'debit',
    cash_pocket: 'USD',
    ...overrides,
  };
}

async function renderBuy(overrides) {
  const transaction = buy(overrides);
  apiMock.get.mockResolvedValue({ transaction, fees: [], taxes: [] });
  render(DetailTransactionModal, { props: { open: true, transaction: { id: transaction.id } } });
  await waitFor(() => expect(screen.getByText('Cash handling')).toBeTruthy());
}

describe('DetailTransactionModal cash pocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(() => cleanup());

  it('shows the pocket that paid when it differs from the row currency', async () => {
    await renderBuy({ cash_pocket: 'JPY' });

    expect(screen.getByText('Cash pocket')).toBeTruthy();
    expect(screen.getByText('JPY')).toBeTruthy();
  });

  it('hides the pocket when it is the row currency', async () => {
    await renderBuy({ cash_pocket: 'USD' });

    expect(screen.queryByText('Cash pocket')).toBeNull();
  });

  it('lists the generated FX legs that funded a buy', async () => {
    const transaction = buy({ id: 7, funding_transaction_ids: [10, 11] });
    apiMock.get.mockReset();
    apiMock.get.mockImplementation((url) => {
      if (url === '/transactions/7/full') {
        return Promise.resolve({ transaction, fees: [], taxes: [] });
      }
      const id = Number(url.split('/').pop());
      return Promise.resolve({
        id,
        timestamp: '2026-11-12T00:00:00',
        type: id === 10 ? 'TRANSFER_OUT' : 'TRANSFER_IN',
        total_value: id === 10 ? 75000 : 500,
        currency: id === 10 ? 'JPY' : 'USD',
      });
    });

    render(DetailTransactionModal, { props: { open: true, transaction: { id: 7 } } });

    await waitFor(() => expect(screen.getByText('Funded by')).toBeTruthy());
    expect(screen.getByText(/75,000\.00/)).toBeTruthy();
  });
});

describe('DetailTransactionModal balance adjustments', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(() => cleanup());

  it('marks a snapshot adjustment as auto, shows its source and hides edit/delete', async () => {
    const transaction = buy({
      id: 126,
      type: 'BALANCE_ADJUSTMENT',
      total_value: 1.08,
      notes: 'Balance adjustment for snapshot at 2026-09-04T02:12:00',
      balance_snapshot_id: 9,
      balance_snapshot_timestamp: '2026-09-04T02:12:00',
      balance_snapshot_amount: 3274.89,
    });
    apiMock.get.mockResolvedValue({ transaction, fees: [], taxes: [] });

    render(DetailTransactionModal, { props: { open: true, transaction: { id: 126 } } });

    await waitFor(() => expect(screen.getByText('Source')).toBeTruthy());
    expect(screen.getByText('Auto')).toBeTruthy();
    expect(screen.getByText(/balance snapshot of/)).toBeTruthy();
    expect(screen.queryByText('Edit')).toBeNull();
    expect(screen.queryByText('Delete')).toBeNull();
  });

  it('labels an inferred-cash adjustment without a snapshot', async () => {
    const transaction = buy({
      id: 127,
      type: 'BALANCE_ADJUSTMENT',
      total_value: 50,
      notes: 'Inferred cash for investment purchases',
      balance_snapshot_id: null,
    });
    apiMock.get.mockResolvedValue({ transaction, fees: [], taxes: [] });

    render(DetailTransactionModal, { props: { open: true, transaction: { id: 127 } } });

    await waitFor(() => expect(screen.getByText('Source')).toBeTruthy());
    expect(screen.getByText(/inferred cash/)).toBeTruthy();
  });
});

describe('DetailTransactionModal currency conversion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(() => cleanup());

  it('shows both sides, the rate and the Auto mark for a generated conversion', async () => {
    const transaction = buy({
      id: 200,
      type: 'FX_CONVERSION',
      currency: 'JPY',
      total_value: 75000,
      payment_currency: 'USD',
      gross_amount: 500,
      fx_rate: 150,
      auto_generated: true,
    });
    apiMock.get.mockResolvedValue({ transaction, fees: [], taxes: [] });

    render(DetailTransactionModal, { props: { open: true, transaction: { id: 200 } } });

    await waitFor(() => expect(screen.getByText('Destination')).toBeTruthy());
    expect(screen.getAllByText('Source').length).toBeGreaterThan(0);
    expect(screen.getByText('Auto')).toBeTruthy();
    expect(screen.getByText(/Generated to fund/)).toBeTruthy();
    expect(screen.getAllByText(/75,000/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/500\.00/).length).toBeGreaterThan(0);
    expect(screen.queryByText('Edit')).toBeNull();
    expect(screen.queryByText('Delete')).toBeNull();
  });

  it('keeps edit and delete for a user-recorded conversion', async () => {
    const transaction = buy({
      id: 201,
      type: 'FX_CONVERSION',
      currency: 'JPY',
      total_value: 10000,
      payment_currency: 'USD',
      gross_amount: 66.67,
      fx_rate: 150,
      auto_generated: false,
    });
    apiMock.get.mockResolvedValue({ transaction, fees: [], taxes: [] });

    render(DetailTransactionModal, { props: { open: true, transaction: { id: 201 } } });

    await waitFor(() => expect(screen.getByText('Destination')).toBeTruthy());
    expect(screen.getByText(/Recorded currency conversion/)).toBeTruthy();
    expect(screen.getByText('Edit')).toBeTruthy();
    expect(screen.getByText('Delete')).toBeTruthy();
  });
});
