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

describe('EditTransactionModal cash handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    apiMock.get.mockResolvedValue({ fees: [], taxes: [] });
    apiMock.put.mockResolvedValue({});
    crudMock.transactions.update.mockResolvedValue({});
  });

  afterEach(cleanup);

  it('shows the resolved Auto hint for an unanchored spend', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...transactionFixture, cash_handling: null, cash_handling_effective: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto — would inject')).toBeTruthy();
  });

  it('shows the snapshot-covered Auto hint when anchored', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...transactionFixture, cash_handling: null, cash_handling_effective: 'debit' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto — snapshot covers this')).toBeTruthy();
  });

  it('always sends cash_handling for investment spends (null keeps Auto)', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...transactionFixture, cash_handling: null, cash_handling_effective: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    await screen.findByText('Auto — would inject');

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/transactions/7/full',
        expect.objectContaining({
          transaction: expect.objectContaining({ cash_handling: null }),
        })
      );
    });
  });

  it('sends back a persisted explicit choice on investment spends', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...transactionFixture, cash_handling: 'inject', cash_handling_effective: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    await screen.findByText('Auto — would inject');

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/transactions/7/full',
        expect.objectContaining({
          transaction: expect.objectContaining({ cash_handling: 'inject' }),
        })
      );
    });
  });

  it('persists an explicit debit choice on plain expenses', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: {
          id: 9,
          type: 'MONEY_OUT',
          timestamp: '2026-01-23T10:00:00',
          entity_id: 1,
          currency: 'EUR',
          total_value: 100,
          cash_handling: 'debit',
          cash_handling_effective: 'debit',
        },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    fireEvent.click(await screen.findByText('Save'));

    await waitFor(() => {
      expect(crudMock.transactions.update).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ cash_handling: 'debit' })
      );
    });
    expect(apiMock.put).not.toHaveBeenCalled();
  });

  it('omits cash_handling for non-spend types', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: {
          id: 11,
          type: 'INCOME',
          timestamp: '2026-01-23T10:00:00',
          entity_id: 1,
          currency: 'EUR',
          total_value: 200,
          income_category: 'salary',
        },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    fireEvent.click(await screen.findByText('Save'));

    await waitFor(() => {
      expect(crudMock.transactions.update).toHaveBeenCalledTimes(1);
    });
    const payload = crudMock.transactions.update.mock.calls[0][1];
    expect(payload.cash_handling).toBeUndefined();
  });
});
