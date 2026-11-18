import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import AddEntityModal from '../components/modals/AddEntityModal.svelte';

const { crudMock } = vi.hoisted(() => ({
  crudMock: { entities: { create: vi.fn(() => Promise.resolve({})) } },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: { getList: vi.fn(() => Promise.resolve(['EUR', 'USD'])) },
}));

vi.mock('$lib/api/analytics.js', () => ({ crud: crudMock, currenciesApi: currenciesMock }));

describe('AddEntityModal currency mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
  });

  afterEach(cleanup);

  async function fill(container, { mainCurrency, multiCurrency }) {
    await waitFor(() => expect(container.querySelectorAll('select').length).toBe(2));
    await waitFor(() => expect(container.querySelectorAll('select')[1].options.length).toBe(3));
    fireEvent.input(container.querySelector('input[type="text"]'), { target: { value: 'Single Bank' } });
    if (mainCurrency) {
      fireEvent.change(container.querySelectorAll('select')[1], { target: { value: mainCurrency } });
    }
    if (!multiCurrency) {
      fireEvent.click(container.querySelector('input[type="checkbox"]'));
    }
  }

  it('submits the multi-currency flag and the main currency', async () => {
    const { container } = render(AddEntityModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });
    await fill(container, { mainCurrency: 'EUR', multiCurrency: false });

    fireEvent.click(screen.getByText('Create'));

    await waitFor(() => expect(crudMock.entities.create).toHaveBeenCalledTimes(1));
    expect(crudMock.entities.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Single Bank',
        main_currency: 'EUR',
        supports_multi_currency: false,
      })
    );
  });

  it('blocks a single-currency entity without a main currency', async () => {
    const { container } = render(AddEntityModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });
    await fill(container, { multiCurrency: false });

    fireEvent.click(screen.getByText('Create'));

    await waitFor(() =>
      expect(screen.getByText('Select the main currency for a single-currency entity.')).toBeTruthy()
    );
    expect(crudMock.entities.create).not.toHaveBeenCalled();
  });

  it('creates a multi-currency entity by default', async () => {
    const { container } = render(AddEntityModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });
    await fill(container, { multiCurrency: true });

    fireEvent.click(screen.getByText('Create'));

    await waitFor(() => expect(crudMock.entities.create).toHaveBeenCalledTimes(1));
    expect(crudMock.entities.create).toHaveBeenCalledWith(
      expect.objectContaining({ supports_multi_currency: true })
    );
  });
});
