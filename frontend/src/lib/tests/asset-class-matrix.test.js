import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import GroupedTable from '../components/GroupedTable.svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { setNumberFormat } from '$lib/preferences/numberFormat.svelte';
import { privacyHidden, togglePrivacy } from '$lib/preferences/privacy.svelte';

const ROWS = [
  // Variable Income: 25.000 (IBKR 20.000, DEGIRO 5.000)
  { entity: 'IBKR', assetClass: 'VI', origAmount: 20000, origCurrency: 'EUR', unifiedAmount: 20000, rateMissing: false },
  { entity: 'DEGIRO', assetClass: 'VI', origAmount: 5000, origCurrency: 'EUR', unifiedAmount: 5000, rateMissing: false },
  // Fixed Income: 15.000 (IBKR 10.000, TR 5.000)
  { entity: 'IBKR', assetClass: 'FI', origAmount: 10000, origCurrency: 'EUR', unifiedAmount: 10000, rateMissing: false },
  { entity: 'TR', assetClass: 'FI', origAmount: 5000, origCurrency: 'EUR', unifiedAmount: 5000, rateMissing: false },
  // Unclassified: 1.000 (DEGIRO)
  { entity: 'DEGIRO', assetClass: null, origAmount: 1000, origCurrency: 'EUR', unifiedAmount: 1000, rateMissing: false },
];

function renderTable(rows = ROWS) {
  return render(GroupedTable, { props: { rows, currencySymbol: '€', currencyCode: 'EUR' } });
}

function rowByLabel(container, label) {
  return [...container.querySelectorAll('tbody tr')].find(
    (tr) => tr.querySelector('th.row-label').textContent.trim() === label,
  );
}

describe('Asset class x entity matrix', () => {
  beforeEach(() => {
    setLocale('en-US');
    setNumberFormat('comma-dot');
    if (privacyHidden()) togglePrivacy();
  });

  afterEach(() => {
    cleanup();
    if (privacyHidden()) togglePrivacy();
  });

  it('orders classes and entities by total, unclassified last', () => {
    const { container } = renderTable();

    const classes = [...container.querySelectorAll('tbody th.row-label')].map((th) => th.textContent.trim());
    expect(classes).toEqual(['Variable Income', 'Fixed Income', 'Unclassified']);

    const entities = [...container.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    expect(entities).toEqual(['Asset Class \\ Entity', 'IBKR', 'DEGIRO', 'TR', 'Total']);
  });

  it('shows the amount and its share of the portfolio in each cell', () => {
    const { container } = renderTable();

    const cell = rowByLabel(container, 'Variable Income').querySelectorAll('td')[0];
    expect(cell.querySelector('.amount').textContent.trim()).toBe('20,000\u00A0€');
    expect(cell.querySelector('.share').textContent.trim()).toBe('48.78%');
    expect(cell.classList.contains('heat-5')).toBe(true);

    const mid = rowByLabel(container, 'Fixed Income').querySelectorAll('td')[0];
    expect(mid.querySelector('.share').textContent.trim()).toBe('24.39%');
    expect(mid.classList.contains('heat-4')).toBe(true);
  });

  it('renders the total column and the grand total', () => {
    const { container } = renderTable();

    const row = rowByLabel(container, 'Variable Income');
    const total = row.querySelector('td.total-col');
    expect(total.querySelector('.amount').textContent.trim()).toBe('25,000\u00A0€');
    expect(total.querySelector('.share').textContent.trim()).toBe('60.98%');

    const footer = container.querySelector('tfoot tr');
    expect(footer.querySelector('.grand-total .amount').textContent.trim()).toBe('41,000\u00A0€');
  });

  it('marks unconverted rows and warns once', () => {
    const { container } = renderTable([
      ...ROWS,
      { entity: 'IBKR', assetClass: 'Monetary', origAmount: 1000000, origCurrency: 'JPY', unifiedAmount: 1000000, rateMissing: true },
    ]);

    const cell = rowByLabel(container, 'Monetary').querySelectorAll('td')[0];
    expect(cell.querySelector('.amount').textContent).toContain('*');
    expect(container.querySelector('.warning').textContent).toContain('JPY');
  });

  it('keeps the percentages while masking the amounts in privacy mode', () => {
    togglePrivacy();
    const { container } = renderTable();

    const cell = rowByLabel(container, 'Variable Income').querySelectorAll('td')[0];
    expect(cell.className).not.toMatch(/heat-/);
    expect(cell.querySelector('.amount').textContent).toContain('********');
    expect(cell.querySelector('.share').textContent.trim()).toBe('48.78%');
  });

  it('hides the total column when there is a single entity', () => {
    const { container } = renderTable([ROWS[0]]);

    const headers = [...container.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    expect(headers).toEqual(['Asset Class \\ Entity', 'IBKR']);
    expect(container.querySelector('.grand-total')).toBeNull();
  });

  it('appends the display currency symbol to every amount', () => {
    const { container } = renderTable();

    const amounts = [...container.querySelectorAll('.amount')];
    expect(amounts.length).toBeGreaterThan(0);
    for (const amount of amounts) {
      expect(amount.textContent.trim().endsWith('€')).toBe(true);
    }
  });
});
