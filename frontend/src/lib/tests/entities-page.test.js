import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/entities/+page.svelte';

const { crudMock, analyticsMock, currenciesMock } = vi.hoisted(() => ({
  crudMock: {
    entities: {
      getList: vi.fn(() => Promise.resolve([])),
      getDependents: vi.fn(() =>
        Promise.resolve({ has_transactions: false, has_balance_snapshots: false, has_schedules: false })
      ),
    },
  },
  analyticsMock: {
    holdingsByEntity: vi.fn(() => Promise.resolve([])),
    historicalByAssetClass: vi.fn(() => Promise.resolve([])),
  },
  currenciesMock: { getList: vi.fn(() => Promise.resolve(['EUR'])) },
}));

vi.mock('$lib/api/analytics.js', () => ({
  crud: crudMock,
  analytics: analyticsMock,
  currenciesApi: currenciesMock,
}));

describe('entities page delete affordance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    crudMock.entities.getList.mockResolvedValue([
      { id: 1, name: 'Broker A', entity_type: 'BROKER', country: null },
      { id: 2, name: 'Broker B', entity_type: 'BROKER', country: null },
    ]);
    crudMock.entities.getDependents.mockImplementation((id) =>
      Promise.resolve({
        has_transactions: id === 1,
        has_balance_snapshots: false,
        has_schedules: false,
      })
    );
  });

  afterEach(cleanup);

  it('drops the warning symbol and explains a disabled delete via its tooltip', async () => {
    const { container } = render(Page);
    await screen.findAllByText('Broker A');

    expect(container.querySelector('.dependents-indicator')).toBeNull();

    const lockedRow = [...container.querySelectorAll('tbody tr')].find((tr) =>
      tr.textContent.includes('Broker A')
    );
    const lockedButton = lockedRow.querySelector('button[disabled]');
    expect(lockedButton).toBeTruthy();
    expect(lockedButton.closest('.icon-btn-tooltip')?.getAttribute('title')).toBe(
      'Cannot delete: this entity has related records.'
    );

    const freeRow = [...container.querySelectorAll('tbody tr')].find((tr) =>
      tr.textContent.includes('Broker B')
    );
    await waitFor(() => expect(freeRow.querySelector('button:not([disabled])')).toBeTruthy());
  });
});
