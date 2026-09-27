import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, screen, waitFor, cleanup, within } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import * as store from '$lib/stores/profile.svelte.js';
import Page from '../../routes/settings/+page.svelte';

const { apiMock } = vi.hoisted(() => {
  const clone = (x) => JSON.parse(JSON.stringify(x));
  let profiles = [{ id: 1, name: 'Default', has_password: false }];
  let taxBases = [];
  let taxDefinitions = [];
  let brokerFees = [];
  let nextBaseId = 1;
  let nextDefId = 1;
  let nextFeeId = 1;
  let failDeleteDefinitionId = null;
  let failSlug = null;

  const ApiError = class extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  };

  return {
    apiMock: {
      get: vi.fn(async (path) => {
        switch (path) {
          case '/profiles': return profiles.map(clone);
          case '/currencies': return ['EUR', 'USD'];
          case '/fiscal-periods': return [];
          case '/tax-bases': return taxBases.map(clone);
          case '/tax-definitions': return taxDefinitions.map(clone);
          case '/broker-fee-definitions': return brokerFees.map(clone);
          default: throw new Error('unexpected GET ' + path);
        }
      }),
      post: vi.fn(async (path, data) => {
        if (path === '/tax-bases') {
          const created = { id: nextBaseId++, ...clone(data), categories: [...data.categories], rates: clone(data.rates) };
          taxBases.push(created);
          return clone(created);
        }
        if (path === '/tax-definitions') {
          if (failSlug && data.slug === failSlug) {
            throw new ApiError(`Tax definition slug '${data.slug}' already exists`, 409);
          }
          const created = { id: nextDefId++, ...clone(data) };
          taxDefinitions.push(created);
          return clone(created);
        }
        if (path === '/broker-fee-definitions') {
          const created = { id: nextFeeId++, ...clone(data) };
          brokerFees.push(created);
          return clone(created);
        }
        if (path === '/profiles') {
          const created = { id: 99, name: data.name, has_password: false };
          profiles.push(created);
          return clone(created);
        }
        throw new Error('unexpected POST ' + path);
      }),
      put: vi.fn(async (path, data) => {
        if (path.startsWith('/tax-bases/')) {
          const id = Number(path.split('/').pop());
          const idx = taxBases.findIndex((x) => x.id === id);
          taxBases[idx] = { id, ...clone(data), categories: [...data.categories], rates: clone(data.rates) };
          return clone(taxBases[idx]);
        }
        if (path.startsWith('/tax-definitions/')) {
          const id = Number(path.split('/').pop());
          const idx = taxDefinitions.findIndex((x) => x.id === id);
          taxDefinitions[idx] = { id, ...clone(data) };
          return clone(taxDefinitions[idx]);
        }
        if (path.startsWith('/broker-fee-definitions/')) {
          const id = Number(path.split('/').pop());
          const idx = brokerFees.findIndex((x) => x.id === id);
          brokerFees[idx] = { id, ...clone(data) };
          return clone(brokerFees[idx]);
        }
        throw new Error('unexpected PUT ' + path);
      }),
      del: vi.fn(async (path) => {
        if (path.startsWith('/tax-bases/')) {
          const id = Number(path.split('/').pop());
          taxBases = taxBases.filter((x) => x.id !== id);
          return null;
        }
        if (path.startsWith('/tax-definitions/')) {
          const id = Number(path.split('/').pop());
          if (failDeleteDefinitionId === id) {
            throw new ApiError(`Tax definition ${id} is referenced by confirmed transaction taxes`, 422);
          }
          taxDefinitions = taxDefinitions.filter((x) => x.id !== id);
          return null;
        }
        if (path.startsWith('/broker-fee-definitions/')) {
          const id = Number(path.split('/').pop());
          brokerFees = brokerFees.filter((x) => x.id !== id);
          return null;
        }
        throw new Error('unexpected DELETE ' + path);
      }),
      patch: vi.fn(async () => ({})),
      __seed(next) {
        taxBases = clone(next.taxBases || []);
        taxDefinitions = clone(next.taxDefinitions || []);
        brokerFees = clone(next.brokerFees || []);
        nextBaseId = Math.max(1, ...taxBases.map((b) => b.id)) + 1;
        nextDefId = Math.max(1, ...taxDefinitions.map((d) => d.id)) + 1;
        nextFeeId = Math.max(1, ...brokerFees.map((f) => f.id)) + 1;
        failDeleteDefinitionId = null;
        failSlug = null;
      },
      __failDeleteDefinition(id) {
        failDeleteDefinitionId = id;
      },
      __failSlug(slug) {
        failSlug = slug;
      },
    },
  };
});

vi.mock('$lib/api/client.js', () => ({
  api: apiMock,
  setActiveProfileId: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  },
}));

const seed = {
  taxBases: [
    {
      id: 1,
      ruleset_key: 'spain',
      name: 'Spain savings',
      computation: 'progressive',
      flat_rate: null,
      year_start: null,
      categories: ['capital_gains', 'dividends'],
      rates: [
        { from_amount: 0, to_amount: 6000, rate: 0.19 },
        { from_amount: 6000, to_amount: null, rate: 0.21 },
      ],
    },
    {
      id: 2,
      ruleset_key: 'japan',
      name: 'Japan flat',
      computation: 'flat',
      flat_rate: 0.20315,
      year_start: null,
      categories: ['capital_gains'],
      rates: [],
    },
  ],
  taxDefinitions: [
    { id: 1, slug: 'stamp_duty', ruleset_key: 'spain', name: 'Tasa Tobin', rate: 0.002, year_start: null },
    { id: 2, slug: 'foreign_withholding', ruleset_key: null, name: 'Foreign withholding', rate: null, year_start: null },
  ],
  brokerFees: [
    { id: 1, name: 'Broker commission' },
    { id: 2, name: 'Transfer fee' },
  ],
};

beforeEach(async () => {
  apiMock.__seed({});
  store.logout();
  sessionStorage.clear();
  await store.loadProfiles();
  vi.clearAllMocks();
  setLocale('en-US');
});

afterEach(cleanup);

describe('Settings tax catalogs', () => {
  it('renders seeded tax bases, definitions and broker fees', async () => {
    apiMock.__seed(seed);
    render(Page);

    await waitFor(() => expect(screen.getByText(/Spain savings/)).toBeTruthy());
    expect(screen.getByText(/Japan flat/)).toBeTruthy();

    const baseRow = screen.getByText(/Spain savings/).closest('.profile-manage-row');
    expect(within(baseRow).getByText(/Progressive/)).toBeTruthy();

    expect(screen.getByText('Tasa Tobin')).toBeTruthy();
    expect(screen.getByText('Foreign withholding')).toBeTruthy();

    const defRow = screen.getByText('Tasa Tobin').closest('.profile-manage-row');
    expect(within(defRow).getByText(/0\.20%/)).toBeTruthy();

    expect(screen.getByText('Broker commission')).toBeTruthy();
    expect(screen.getByText('Transfer fee')).toBeTruthy();
  });

  it('renders the localized capital-gains category label, not the raw key', async () => {
    render(Page);

    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/tax-bases'));
    await fireEvent.click(screen.getByRole('button', { name: 'Add base' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add tax base' });

    expect(within(dialog).getByText('Capital gains')).toBeTruthy();
    expect(within(dialog).queryByText('taxBases.category.capital_gains')).toBeNull();
  });

  it('shows the Year start tooltip in the tax base modal', async () => {
    render(Page);

    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/tax-bases'));
    await fireEvent.click(screen.getByRole('button', { name: 'Add base' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add tax base' });

    expect(
      within(dialog).getByText(
        'First fiscal year this base applies to. Leave empty to apply to all years — the most recent matching base wins.',
      ),
    ).toBeTruthy();
  });

  it('shows empty states when the catalogs are empty', async () => {
    render(Page);

    await waitFor(() => expect(screen.getByText('No tax bases configured. The tax page falls back to computed defaults.')).toBeTruthy());
    expect(screen.getByText('No tax definitions configured. Taxes are confirmed manually on each transaction.')).toBeTruthy();
    expect(screen.getByText('No broker fee definitions configured.')).toBeTruthy();
  });

  it('creates a progressive tax base with one bracket', async () => {
    render(Page);
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/tax-bases'));

    await fireEvent.click(screen.getByRole('button', { name: 'Add base' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add tax base' });

    await fireEvent.input(within(dialog).getByLabelText('Name'), { target: { value: 'Spain savings 2026' } });
    await fireEvent.input(within(dialog).getByLabelText('From'), { target: { value: '0' } });
    await fireEvent.input(within(dialog).getByLabelText('Rate (0–1)'), { target: { value: '0.19' } });

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/tax-bases', {
      ruleset_key: 'spain',
      name: 'Spain savings 2026',
      computation: 'progressive',
      flat_rate: null,
      year_start: null,
      categories: ['capital_gains'],
      rates: [{ from_amount: 0, to_amount: null, rate: 0.19 }],
    }));
  });

  it('creates a flat tax base with no brackets', async () => {
    render(Page);
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/tax-bases'));

    await fireEvent.click(screen.getByRole('button', { name: 'Add base' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add tax base' });

    await fireEvent.input(within(dialog).getByLabelText('Name'), { target: { value: 'Japan 2026' } });
    await fireEvent.change(within(dialog).getByLabelText('Computation'), { target: { value: 'flat' } });
    await fireEvent.input(within(dialog).getByLabelText('Flat rate (0–1)'), { target: { value: '0.2' } });

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/tax-bases', {
      ruleset_key: 'spain',
      name: 'Japan 2026',
      computation: 'flat',
      flat_rate: 0.2,
      year_start: null,
      categories: ['capital_gains'],
      rates: [],
    }));
  });

  it('edits a tax base through the modal', async () => {
    apiMock.__seed(seed);
    render(Page);
    await waitFor(() => expect(screen.getByText(/Spain savings/)).toBeTruthy());

    const baseRow = screen.getByText(/Spain savings/).closest('.profile-manage-row');
    await fireEvent.click(within(baseRow).getByRole('button', { name: 'Edit' }));

    const dialog = await screen.findByRole('dialog', { name: 'Edit tax base' });
    await fireEvent.input(within(dialog).getByLabelText('Name'), { target: { value: 'Spain savings v2' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(apiMock.put).toHaveBeenCalledWith('/tax-bases/1', expect.objectContaining({
      name: 'Spain savings v2',
      computation: 'progressive',
      flat_rate: null,
    })));
    await waitFor(() => expect(screen.getByText(/Spain savings v2/)).toBeTruthy());
  });

  it('deletes a tax base after confirmation', async () => {
    apiMock.__seed(seed);
    render(Page);
    await waitFor(() => expect(screen.getByText(/Japan flat/)).toBeTruthy());

    const baseRow = screen.getByText(/Japan flat/).closest('.profile-manage-row');
    await fireEvent.click(within(baseRow).getByRole('button', { name: 'Delete' }));

    const dialog = await screen.findByRole('dialog', { name: 'Delete tax base' });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(apiMock.del).toHaveBeenCalledWith('/tax-bases/2'));
    await waitFor(() => expect(screen.queryByText(/Japan flat/)).toBeNull());
  });

  it('keeps the delete dialog open and shows the message when a definition is in use', async () => {
    apiMock.__seed(seed);
    apiMock.__failDeleteDefinition(1);
    render(Page);
    await waitFor(() => expect(screen.getByText('Tasa Tobin')).toBeTruthy());

    const defRow = screen.getByText('Tasa Tobin').closest('.profile-manage-row');
    await fireEvent.click(within(defRow).getByRole('button', { name: 'Delete' }));

    const dialog = await screen.findByRole('dialog', { name: 'Delete tax definition' });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(within(dialog).getByText('Tax definition 1 is referenced by confirmed transaction taxes')).toBeTruthy());
    expect(screen.getByRole('dialog', { name: 'Delete tax definition' })).toBeTruthy();
    expect(screen.getByText('Tasa Tobin')).toBeTruthy();
  });

  it('shows the slug-conflict message inline when creating a definition', async () => {
    apiMock.__seed(seed);
    apiMock.__failSlug('stamp_duty');
    render(Page);
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/tax-definitions'));

    await fireEvent.click(screen.getByRole('button', { name: 'Add definition' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add tax definition' });

    await fireEvent.input(within(dialog).getByLabelText('Name'), { target: { value: 'Stamp Duty' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(within(dialog).getByText("Tax definition slug 'stamp_duty' already exists")).toBeTruthy());
    expect(screen.getByRole('dialog', { name: 'Add tax definition' })).toBeTruthy();
  });

  it('creates a broker fee definition', async () => {
    render(Page);
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/broker-fee-definitions'));

    await fireEvent.click(screen.getByRole('button', { name: 'Add fee' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add broker fee' });

    await fireEvent.input(within(dialog).getByLabelText('Name'), { target: { value: 'FX conversion' } });
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/broker-fee-definitions', { name: 'FX conversion' }));
    await waitFor(() => expect(screen.getByText('FX conversion')).toBeTruthy());
  });
});