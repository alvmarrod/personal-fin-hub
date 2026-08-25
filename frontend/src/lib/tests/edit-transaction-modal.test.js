import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import EditTransactionModal from '../components/modals/EditTransactionModal.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    transactions: { update: vi.fn() },
    entities: { getList: vi.fn(() => Promise.resolve([{ id: 1, name: 'TEF' }])) },
    portfolioAssets: { getList: vi.fn(() => Promise.resolve([])) },
    fiscalExemptions: { getList: vi.fn(() => Promise.resolve([])) },
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: {
    getList: vi.fn(() => Promise.resolve(['EUR', 'USD'])),
  },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));
vi.mock('$lib/api/analytics.js', () => ({
  crud: crudMock,
  currenciesApi: currenciesMock,
}));

const transactionFixture = {
  id: 7,
  type: 'INVESTMENT_BUY',
  timestamp: '2026-01-23T10:00:00',
  entity_id: 1,
  currency: 'EUR',
  total_value: 500,
  quantity: 10,
  unit_price: 50,
  portfolio_asset_id: 5,
};

function renderModal() {
  return render(EditTransactionModal, {
    props: {
      open: true,
      transaction: transactionFixture,
      onclose: () => {},
      onsuccess: () => {},
    },
  });
}

describe('EditTransactionModal fee removal persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    apiMock.get.mockResolvedValue({
      fees: [
        { fee_type: 'BROKER', nature: 'FIXED', fixed_amount: 1.5, percentage: 0, currency: 'EUR' },
      ],
      taxes: [],
    });
    apiMock.put.mockResolvedValue({});
  });

  afterEach(cleanup);

  it('routes investment saves through PUT /full even when all fees are removed', async () => {
    renderModal();

    const removeFeeBtn = await screen.findByRole('button', { name: 'Remove fee' });
    fireEvent.click(removeFeeBtn);
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Remove fee' })).toBeNull();
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledTimes(1);
    });
    expect(apiMock.put).toHaveBeenCalledWith(
      '/transactions/7/full',
      expect.objectContaining({ fees: [], taxes: [] })
    );
    expect(crudMock.transactions.update).not.toHaveBeenCalled();
  });

  it('keeps using PUT /full when fees remain', async () => {
    renderModal();
    await screen.findByRole('button', { name: 'Remove fee' });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/transactions/7/full',
        expect.objectContaining({
          fees: [
            expect.objectContaining({ fee_type: 'BROKER' }),
          ],
        })
      );
    });
    expect(crudMock.transactions.update).not.toHaveBeenCalled();
  });
});
