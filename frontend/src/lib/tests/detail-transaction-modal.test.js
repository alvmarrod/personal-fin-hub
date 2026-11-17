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
});
