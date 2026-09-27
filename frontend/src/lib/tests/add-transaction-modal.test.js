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
    transactions: { create: vi.fn() },
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
});