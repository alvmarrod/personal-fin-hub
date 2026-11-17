import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { setDisplayTimezone } from '$lib/preferences/timezone.svelte';
import { fromZonedInput } from '$lib/utils/time.js';
import AddBalanceSnapshotModal from '../components/modals/AddBalanceSnapshotModal.svelte';

const { crudMock } = vi.hoisted(() => ({
  crudMock: {
    entities: { getList: vi.fn(() => Promise.resolve([{ id: 1, name: 'Broker' }, { id: 2, name: 'Bank' }])) },
    balanceSnapshots: { create: vi.fn(() => Promise.resolve({})) },
  },
}));

const { currenciesMock } = vi.hoisted(() => ({
  currenciesMock: { getList: vi.fn(() => Promise.resolve(['EUR', 'USD'])) },
}));

vi.mock('$lib/api/analytics.js', () => ({ crud: crudMock, currenciesApi: currenciesMock }));

describe('AddBalanceSnapshotModal timezone handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    setDisplayTimezone('Asia/Tokyo');
  });

  afterEach(() => {
    cleanup();
    setDisplayTimezone('UTC');
  });

  async function renderAndFill(container) {
    await waitFor(() => {
      const selects = container.querySelectorAll('select');
      expect(selects.length).toBe(2);
      expect(selects[0].options.length).toBe(2);
      expect(selects[1].options.length).toBe(2);
    });
    fireEvent.change(container.querySelectorAll('select')[0], { target: { value: '2' } });
    fireEvent.change(container.querySelectorAll('select')[1], { target: { value: 'USD' } });
    fireEvent.change(container.querySelector('input[type="number"]'), { target: { value: '1000' } });
  }

  it('prefills the clock in the profile timezone and names that zone', async () => {
    const { container } = render(AddBalanceSnapshotModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });

    const input = container.querySelector('input[type="datetime-local"]');
    // The value is a Tokyo wall clock, so it resolves back to roughly "now" in UTC.
    const resolved = fromZonedInput(input.value, 'Asia/Tokyo').getTime();
    expect(Math.abs(resolved - Date.now())).toBeLessThan(120_000);

    expect(screen.getByText(/Time in Asia\/Tokyo/)).toBeTruthy();
  });

  it('submits the UTC instant of the wall clock it displays', async () => {
    const { container } = render(AddBalanceSnapshotModal, {
      props: { open: true, onclose: () => {}, onsuccess: () => {} },
    });
    await renderAndFill(container);

    const input = container.querySelector('input[type="datetime-local"]');
    fireEvent.input(input, { target: { value: '2026-11-17T09:30' } });

    fireEvent.click(screen.getByText('Create'));

    await waitFor(() => {
      expect(crudMock.balanceSnapshots.create).toHaveBeenCalledTimes(1);
    });
    expect(crudMock.balanceSnapshots.create.mock.calls[0][0].timestamp).toBe('2026-11-17T00:30:00.000Z');
  });
});
