import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import AddTransactionModal from '../components/modals/AddTransactionModal.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
  },
}));

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    transactions: { create: vi.fn(), heldAssets: vi.fn(() => Promise.resolve([])) },
    entities: { getList: vi.fn(() => Promise.resolve([{ id: 1, name: 'TEF' }])) },
    portfolioAssets: {
      getList: vi.fn(() => Promise.resolve([{ id: 9, market_code: 'VWCE.DE', name: 'Vanguard' }])),
    },
    fiscalExemptions: { getList: vi.fn(() => Promise.resolve([])) },
    fiscalPeriods: { getList: vi.fn(() => Promise.resolve([])) },
    taxDefinitions: {
      getList: vi.fn(() => Promise.resolve([
        { id: 12, slug: 'foreign_withholding', name: 'Foreign Withholding', ruleset_key: null },
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

function findSelectByOption(container, optionText) {
  return [...container.querySelectorAll('select')].find((s) =>
    [...s.options].some((o) => o.textContent.includes(optionText))
  );
}

async function fillDividendRequired(container) {
  await waitFor(() => {
    expect(container.querySelectorAll('select').length).toBeGreaterThan(3);
  });
  fireEvent.input(container.querySelectorAll('input[type="date"]')[0], {
    target: { value: '2026-01-23' },
  });
  fireEvent.change(container.querySelectorAll('select')[1], { target: { value: '1' } });
  fireEvent.input(container.querySelector('input[type="number"]'), {
    target: { value: '100' },
  });
  const assetSelect = findSelectByOption(container, 'VWCE');
  fireEvent.change(assetSelect, { target: { value: '9' } });
  await waitFor(() => {
    expect(findSelectByOption(container, 'VWCE').value).toBe('9');
  });
}

async function clickAddTransaction(container) {
  const btn = await waitFor(() => {
    const found = [...container.querySelectorAll('button')].find((b) =>
      b.textContent.trim() === 'Add Transaction'
    );
    expect(found).toBeTruthy();
    return found;
  });
  fireEvent.click(btn);
}

function renderDividendAdd(props = {}) {
  return render(AddTransactionModal, {
    props: {
      open: true,
      defaultType: 'INCOME',
      defaultCategory: 'dividends',
      onclose: () => {},
      onsuccess: () => {},
      ...props,
    },
  });
}

describe('AddTransactionModal sell limit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    apiMock.post.mockResolvedValue({});
    crudMock.transactions.create.mockResolvedValue({});
    crudMock.portfolioAssets.getList.mockResolvedValue([
      { id: 9, market_code: 'VWCE.DE', name: 'Vanguard' },
      { id: 10, market_code: 'AAPL.US', name: 'Apple' },
    ]);
  });

  afterEach(cleanup);

  function renderSell() {
    return render(AddTransactionModal, {
      props: {
        open: true,
        defaultType: 'INVESTMENT_SELL',
        onclose: () => {},
        onsuccess: () => {},
      },
    });
  }

  async function pickEntity(container) {
    await waitFor(() => {
      expect(container.querySelectorAll('select').length).toBeGreaterThan(3);
    });
    fireEvent.input(container.querySelectorAll('input[type="date"]')[0], {
      target: { value: '2026-01-23' },
    });
    fireEvent.change(container.querySelectorAll('select')[1], { target: { value: '1' } });
  }

  it('filters the asset list to the entity holdings', async () => {
    crudMock.transactions.heldAssets.mockResolvedValue([{ portfolio_asset_id: 9, quantity: 5 }]);
    const { container } = renderSell();
    await pickEntity(container);

    await waitFor(() => {
      const assetSelect = findSelectByOption(container, 'VWCE');
      expect([...assetSelect.options].map((o) => o.value)).toEqual(['', '9']);
    });
    expect(crudMock.transactions.heldAssets).toHaveBeenCalledWith(1, expect.any(String));
  });

  it('shows the held quantity and blocks a larger sell', async () => {
    crudMock.transactions.heldAssets.mockResolvedValue([{ portfolio_asset_id: 9, quantity: 5 }]);
    const { container } = renderSell();
    await pickEntity(container);

    fireEvent.change(findSelectByOption(container, 'VWCE'), { target: { value: '9' } });
    await waitFor(() => expect(screen.getByText('Available: 5')).toBeTruthy());

    const numbers = container.querySelectorAll('input[type="number"]');
    fireEvent.input(numbers[1], { target: { value: '6' } });
    fireEvent.input(numbers[2], { target: { value: '100' } });

    await clickAddTransaction(container);
    await waitFor(() =>
      expect(screen.getByText('Quantity exceeds the 5 units this entity holds')).toBeTruthy()
    );
    expect(crudMock.transactions.create).not.toHaveBeenCalled();
  });

  it('hints when the entity holds nothing at the selected date', async () => {
    crudMock.transactions.heldAssets.mockResolvedValue([]);
    const { container } = renderSell();
    await pickEntity(container);

    await waitFor(() =>
      expect(screen.getByText('This entity holds no assets at the selected date')).toBeTruthy()
    );
  });
});

describe('AddTransactionModal catalog-backed taxes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    apiMock.post.mockResolvedValue({});
    crudMock.transactions.create.mockResolvedValue({});
  });

  afterEach(cleanup);

  it('routes a dividend with confirmed withholding through /transactions/full', async () => {
    const { container } = renderDividendAdd();

    await fillDividendRequired(container);

    fireEvent.click(await screen.findByText('+ Add Tax'));
    await waitFor(() => {
      expect(container.querySelector('.tax-row')).not.toBeNull();
    });
    const defSelect = findSelectByOption(container, 'Foreign Withholding');
    expect(defSelect).toBeTruthy();
    fireEvent.change(defSelect, { target: { value: '12' } });
    fireEvent.input(container.querySelectorAll('.tax-row input[type="number"]')[1], {
      target: { value: '5' },
    });

    await clickAddTransaction(container);

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/transactions/full',
        expect.objectContaining({
          transaction: expect.objectContaining({ income_category: 'dividends' }),
          taxes: [
            expect.objectContaining({ tax_definition_id: 12, tax_amount: 5, currency: 'EUR' }),
          ],
        })
      );
    });
    expect(crudMock.transactions.create).not.toHaveBeenCalled();
  });

  it('keeps a dividend without taxes on the plain transactions.create path', async () => {
    const { container } = renderDividendAdd();

    await fillDividendRequired(container);
    await clickAddTransaction(container);

    await waitFor(() => {
      expect(crudMock.transactions.create).toHaveBeenCalledTimes(1);
    });
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it('hides the taxes editor for a plain income row', async () => {
    render(AddTransactionModal, {
      props: {
        open: true,
        onclose: () => {},
        onsuccess: () => {},
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('+ Add Tax')).toBeNull();
    });
  });

  it('disables the add-tax button and hints when the catalog is empty', async () => {
    crudMock.taxDefinitions.getList.mockResolvedValue([]);
    const { container } = renderDividendAdd();

    await waitFor(() => {
      const addTax = [...container.querySelectorAll('button')].find((b) =>
        b.textContent.trim() === '+ Add Tax'
      );
      expect(addTax.disabled).toBe(true);
    });
    expect(
      screen.getByText('No tax definitions catalogued. Define them in Settings to attach taxes.')
    ).toBeTruthy();
  });

  it('does not warn when the type is selected from a fresh form', async () => {
    const { container } = render(AddTransactionModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });
    await waitFor(() => expect(container.querySelectorAll('select').length).toBeGreaterThan(3));

    const typeSelect = findSelectByOption(container, 'Buy');
    fireEvent.change(typeSelect, { target: { value: 'INVESTMENT_BUY' } });

    await waitFor(() => expect(typeSelect.value).toBe('INVESTMENT_BUY'));
    expect(screen.queryByText(/Transaction type changed/)).toBeNull();
  });

  it('clears the sell-only payment currency when switching to a buy', async () => {
    crudMock.entities.getList.mockResolvedValue([{ id: 1, name: 'IBKR', main_currency: 'JPY' }]);
    currenciesMock.getList.mockResolvedValue(['EUR', 'USD', 'JPY']);
    const { container } = render(AddTransactionModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });

    await waitFor(() => {
      expect(container.querySelectorAll('select').length).toBeGreaterThan(3);
    });

    const typeSelect = findSelectByOption(container, 'Sell');
    fireEvent.change(typeSelect, { target: { value: 'INVESTMENT_SELL' } });
    const entitySelect = findSelectByOption(container, 'IBKR');
    fireEvent.change(entitySelect, { target: { value: '1' } });

    const paymentSelect = () => findSelectByOption(container, 'Same as currency');
    await waitFor(() => expect(paymentSelect().value).toBe('JPY'));

    fireEvent.change(typeSelect, { target: { value: 'INVESTMENT_BUY' } });

    await waitFor(() => expect(paymentSelect().value).toBe(''));
    expect(screen.getByText('Transaction type changed: payment mode and payment currency were reset. Review them before saving.')).toBeTruthy();
  });
});
describe('AddTransactionModal single-currency entity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    crudMock.entities.getList.mockResolvedValue([
      { id: 1, name: 'Single Bank', main_currency: 'EUR', supports_multi_currency: false },
    ]);
    crudMock.portfolioAssets.getList.mockResolvedValue([
      { id: 9, market_code: 'VWCE.DE', name: 'Vanguard' },
    ]);
  });

  afterEach(cleanup);

  async function selectEntity(container) {
    await waitFor(() => expect(container.querySelectorAll('select').length).toBeGreaterThan(3));
    const entitySelect = findSelectByOption(container, 'Single Bank');
    fireEvent.change(entitySelect, { target: { value: '1' } });
    await waitFor(() => expect(entitySelect.value).toBe('1'));
  }

  it('locks a buy pocket to the main currency', async () => {
    const { container } = render(AddTransactionModal, {
      props: { open: true, defaultType: 'INVESTMENT_BUY', onclose: () => {}, onsuccess: () => {} },
    });
    await selectEntity(container);

    const pocket = await waitFor(() => {
      const found = [...container.querySelectorAll('select')].find((s) => s.value === 'EUR' && s.disabled);
      expect(found).toBeTruthy();
      return found;
    });
    expect(pocket.disabled).toBe(true);
    expect(screen.getByText('Single-currency entity: EUR')).toBeTruthy();
  });

  it('locks the currency of an expense to the main currency', async () => {
    const { container } = render(AddTransactionModal, {
      props: { open: true, defaultType: 'MONEY_OUT', onclose: () => {}, onsuccess: () => {} },
    });
    await selectEntity(container);

    const currency = await waitFor(() => {
      const found = [...container.querySelectorAll('select')].find((s) => s.value === 'EUR' && s.disabled);
      expect(found).toBeTruthy();
      return found;
    });
    expect(currency.disabled).toBe(true);
  });

  it('leaves the pocket free for a multi-currency entity', async () => {
    crudMock.entities.getList.mockResolvedValue([
      { id: 2, name: 'Multi Broker', main_currency: 'EUR', supports_multi_currency: true },
    ]);
    const { container } = render(AddTransactionModal, {
      props: { open: true, defaultType: 'INVESTMENT_BUY', onclose: () => {}, onsuccess: () => {} },
    });
    await waitFor(() => expect(container.querySelectorAll('select').length).toBeGreaterThan(3));
    const entitySelect = findSelectByOption(container, 'Multi Broker');
    fireEvent.change(entitySelect, { target: { value: '2' } });
    await waitFor(() => expect(entitySelect.value).toBe('2'));

    expect([...container.querySelectorAll('select')].some((s) => s.disabled && s.value === 'EUR')).toBe(false);
    expect(screen.queryByText('Single-currency entity: EUR')).toBeNull();
  });
});
