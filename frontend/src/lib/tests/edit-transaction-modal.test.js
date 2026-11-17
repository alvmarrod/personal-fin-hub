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
    transactions: { update: vi.fn(), heldAssets: vi.fn(() => Promise.resolve([])) },
    entities: { getList: vi.fn(() => Promise.resolve([{ id: 1, name: 'TEF' }])) },
    portfolioAssets: { getList: vi.fn(() => Promise.resolve([])) },
    fiscalExemptions: { getList: vi.fn(() => Promise.resolve([])) },
    fiscalPeriods: { getList: vi.fn(() => Promise.resolve([])) },
    taxDefinitions: {
      getList: vi.fn(() => Promise.resolve([
        { id: 2, slug: 'stamp_duty', name: 'Stamp Duty', ruleset_key: null },
      ])),
    },
    brokerFeeDefinitions: {
      getList: vi.fn(() => Promise.resolve([{ id: 1, name: 'Commission' }])),
    },
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

  it('keeps the tax_definition_id on loaded taxes in the PUT /full payload', async () => {
    apiMock.get.mockResolvedValue({
      fees: [],
      taxes: [{ id: 11, tax_definition_id: 2, tax_rate: 0.19, tax_amount: 9.5, currency: 'EUR' }],
    });
    renderModal();

    fireEvent.click(await screen.findByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/transactions/7/full',
        expect.objectContaining({
          taxes: [
            expect.objectContaining({
              tax_definition_id: 2,
              tax_rate: 0.19,
              tax_amount: 9.5,
              currency: 'EUR',
            }),
          ],
        })
      );
    });
    expect(crudMock.transactions.update).not.toHaveBeenCalled();
  });

  it('routes a dividend with confirmed withholding through PUT /full', async () => {
    apiMock.get.mockResolvedValue({
      fees: [],
      taxes: [{ id: 12, tax_definition_id: 2, tax_rate: null, tax_amount: 5.0, currency: 'EUR' }],
    });
    crudMock.transactions.update.mockResolvedValue({});
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: {
          id: 8,
          type: 'INCOME',
          timestamp: '2026-01-23T10:00:00',
          entity_id: 1,
          currency: 'EUR',
          total_value: 200,
          income_category: 'dividends',
          portfolio_asset_id: 5,
        },
        onclose: () => {},
        onsuccess: () => {},
      },
    });

    fireEvent.click(await screen.findByText('Save'));

    await waitFor(() => {
      expect(apiMock.put).toHaveBeenCalledWith(
        '/transactions/8/full',
        expect.objectContaining({
          taxes: [
            expect.objectContaining({ tax_definition_id: 2, tax_amount: 5.0 }),
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

  const spendFixture = {
    ...transactionFixture,
    type: 'MONEY_OUT',
    portfolio_asset_id: null,
    quantity: null,
    unit_price: null,
  };

  it('falls back to the plain Auto label when the API sends no effect', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...spendFixture, cash_handling: null },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto (recommended)')).toBeTruthy();
  });

  it('shows the injected Auto hint when the spend injected cash', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...spendFixture, cash_handling: null, cash_effect: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto — inferred cash injected')).toBeTruthy();
  });

  it('shows the debited Auto hint when the cash was there', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...spendFixture, cash_handling: null, cash_effect: 'debit' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto — debited from the balance')).toBeTruthy();
  });

  it('shows the absorbed Auto hint when a later snapshot anchors the pocket', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...spendFixture, cash_handling: null, cash_effect: 'absorbed' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    expect(await screen.findByText('Auto — absorbed by a later balance snapshot')).toBeTruthy();
  });

  it('always sends cash_handling for investment spends (null keeps Auto)', async () => {
    render(EditTransactionModal, {
      props: {
        open: true,
        transaction: { ...transactionFixture, cash_handling: null, cash_effect: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    await screen.findByText('Auto — pocket, main currency, then inject the rest');

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
        transaction: { ...transactionFixture, cash_handling: 'inject' },
        onclose: () => {},
        onsuccess: () => {},
      },
    });
    await screen.findByText('Auto — pocket, main currency, then inject the rest');

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

const sellFixture = {
  id: 8,
  type: 'INVESTMENT_SELL',
  timestamp: '2026-01-23T10:00:00',
  entity_id: 1,
  currency: 'EUR',
  total_value: 300,
  quantity: 3,
  unit_price: 100,
  portfolio_asset_id: 5,
};

function inputByLabel(container, label) {
  const field = [...container.querySelectorAll('.form-field')].find(
    (f) => f.querySelector('.form-label-text')?.textContent.trim() === label
  );
  return field?.querySelector('input');
}

describe('EditTransactionModal sell limit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    apiMock.get.mockResolvedValue({ fees: [], taxes: [] });
    apiMock.put.mockResolvedValue({});
    crudMock.transactions.update.mockResolvedValue({});
    crudMock.portfolioAssets.getList.mockResolvedValue([
      { id: 5, market_code: 'VWCE.DE', name: 'Vanguard' },
      { id: 9, market_code: 'AAPL.US', name: 'Apple' },
    ]);
  });

  afterEach(cleanup);

  function renderSell() {
    return render(EditTransactionModal, {
      props: {
        open: true,
        transaction: sellFixture,
        onclose: () => {},
        onsuccess: () => {},
      },
    });
  }

  it('asks for the holding of the sell entity, excluding the edited row', async () => {
    crudMock.transactions.heldAssets.mockResolvedValue([{ portfolio_asset_id: 5, quantity: 4 }]);
    renderSell();

    await waitFor(() => {
      expect(crudMock.transactions.heldAssets).toHaveBeenCalledWith(1, expect.any(String), 8);
    });
    expect(await screen.findByText('Available: 4')).toBeTruthy();
  });

  it('keeps the transaction asset selectable and blocks a quantity above the holding', async () => {
    crudMock.transactions.heldAssets.mockResolvedValue([{ portfolio_asset_id: 5, quantity: 2 }]);
    const { container } = renderSell();

    await screen.findByText('Available: 2');
    const assetSelect = [...container.querySelectorAll('select')].find((s) =>
      [...s.options].some((o) => o.textContent.includes('VWCE'))
    );
    expect([...assetSelect.options].map((o) => o.value)).toEqual(['', '5']);

    fireEvent.input(inputByLabel(container, 'Quantity'), { target: { value: '3' } });
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() =>
      expect(screen.getByText('Quantity exceeds the 2 units this entity holds')).toBeTruthy()
    );
    expect(crudMock.transactions.update).not.toHaveBeenCalled();
    expect(apiMock.put).not.toHaveBeenCalled();
  });
});
