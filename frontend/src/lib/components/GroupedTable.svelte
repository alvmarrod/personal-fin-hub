<script>
  import { t, locale } from '$lib/i18n/index.svelte';
  import { formatAmount, formatPercent, maskAmount } from '$lib/utils/format.svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { assetClassLabel } from '$lib/utils/assetClass.js';

  let { rows = [], currencySymbol = '', currencyCode = '' } = $props();

  const UNCLASSIFIED = '';

  let masked = $derived(privacyHidden());

  let cells = $derived.by(() => {
    const byEntity = new Map();
    for (const row of rows) {
      const entity = row.entity;
      const cls = row.assetClass || UNCLASSIFIED;
      if (!byEntity.has(entity)) byEntity.set(entity, new Map());
      const byClass = byEntity.get(entity);
      const cell = byClass.get(cls) || { value: 0, native: [], rateMissing: false };
      cell.value += row.unifiedAmount || 0;
      cell.native.push({ amount: row.origAmount, currency: row.origCurrency });
      cell.rateMissing = cell.rateMissing || !!row.rateMissing;
      byClass.set(cls, cell);
    }
    return byEntity;
  });

  let entityTotals = $derived.by(() => {
    const totals = new Map();
    for (const [entity, byClass] of cells) {
      let total = 0;
      for (const cell of byClass.values()) total += cell.value;
      totals.set(entity, total);
    }
    return totals;
  });

  let classTotals = $derived.by(() => {
    const totals = new Map();
    for (const byClass of cells.values()) {
      for (const [cls, cell] of byClass) {
        totals.set(cls, (totals.get(cls) || 0) + cell.value);
      }
    }
    return totals;
  });

  let entityNames = $derived(
    [...entityTotals.keys()].sort((a, b) => entityTotals.get(b) - entityTotals.get(a) || a.localeCompare(b, locale())),
  );

  let classKeys = $derived(
    [...classTotals.keys()].sort((a, b) => classTotals.get(b) - classTotals.get(a) || a.localeCompare(b, locale())),
  );

  let grandTotal = $derived([...classTotals.values()].reduce((sum, value) => sum + value, 0));

  let missingCurrencies = $derived([
    ...new Set(rows.filter((row) => row.rateMissing).map((row) => row.origCurrency)),
  ]);

  function share(value) {
    if (!grandTotal) return 0;
    return value / grandTotal;
  }

  /** Percentage text and heat bin use the same 2-decimal rounding. */
  function roundedShare(value) {
    const pct = share(value) * 100;
    return Math.round(pct * 100) / 100 / 100;
  }

  function heat(value) {
    const pct = roundedShare(value);
    if (!pct) return '';
    if (pct < 0.01) return 'heat-1';
    if (pct < 0.05) return 'heat-2';
    if (pct < 0.15) return 'heat-3';
    if (pct < 0.3) return 'heat-4';
    return 'heat-5';
  }

  function cellOf(entity, cls) {
    return cells.get(entity)?.get(cls);
  }

  function amountText(value) {
    const suffix = currencySymbol ? `\u00A0${currencySymbol}` : '';
    return `${masked ? maskAmount() : formatAmount(value)}${suffix}`;
  }

  function shareText(value) {
    if (masked) return maskAmount();
    return formatPercent(roundedShare(value) * 100);
  }

  function nativeText(cell) {
    if (!cell?.native?.length) return '';
    const parts = cell.native
      .filter((item) => item.currency && item.currency !== currencyCode)
      .map((item) => `${formatAmount(item.amount)} ${item.currency}`);
    return parts.join(' + ');
  }

  function cellTitle(entity, cls, cell) {
    if (!cell || masked) return '';
    const parts = [];
    const native = nativeText(cell);
    if (native) parts.push(native);
    parts.push(
      t('dashboard.cellShare', {
        rowShare: formatPercent(roundedShare(classTotals.get(cls)) * 100),
        rowName: assetClassLabel(cls),
        colShare: formatPercent(roundedShare(entityTotals.get(entity)) * 100),
        colName: entity,
      }),
    );
    if (cell.rateMissing) {
      parts.push(t('dashboard.rateMissing', { currency: cell.native[0]?.currency || currencyCode }));
    }
    return parts.join(' · ');
  }

  function totalTitle(value) {
    if (masked) return '';
    return t('dashboard.shareOfPortfolioValue', { share: formatPercent(roundedShare(value) * 100) });
  }

  const LEGEND = [
    { cls: 'heat-1', key: 'dashboard.legendUnder1' },
    { cls: 'heat-2', key: 'dashboard.legend1to5' },
    { cls: 'heat-3', key: 'dashboard.legend5to15' },
    { cls: 'heat-4', key: 'dashboard.legend15to30' },
    { cls: 'heat-5', key: 'dashboard.legendOver30' },
  ];
</script>

<div class="matrix">
  <div class="matrix-scroll">
    <table class="matrix-table">
      <thead>
        <tr>
          <th class="row-label corner" scope="col">{t('dashboard.assetClassCol')} \ {t('dashboard.entityCol')}</th>
          {#each entityNames as entity (entity)}
            <th scope="col">{entity}</th>
          {/each}
          {#if entityNames.length > 1}
            <th class="total-col" scope="col">{t('dashboard.tableTotal')}</th>
          {/if}
        </tr>
      </thead>
      <tbody>
        {#each classKeys as cls (cls)}
          <tr>
            <th class="row-label" scope="row">{assetClassLabel(cls)}</th>
            {#each entityNames as entity (entity)}
              {@const cell = cellOf(entity, cls)}
              <td
                class="num {masked ? '' : heat(cell?.value || 0)}"
                class:empty={!cell}
                title={cellTitle(entity, cls, cell)}
              >
                {#if !cell}
                  <span class="dash">—</span>
                {:else}
                  <span class="amount">
                    {amountText(cell.value)}{#if cell.rateMissing && !masked}<span class="flag" aria-hidden="true">*</span>{/if}
                  </span>
                  <span class="share">{shareText(cell.value)}</span>
                {/if}
              </td>
            {/each}
            {#if entityNames.length > 1}
              <td class="num total-col" title={totalTitle(classTotals.get(cls))}>
                <span class="amount">{amountText(classTotals.get(cls))}</span>
                <span class="share">{shareText(classTotals.get(cls))}</span>
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <th class="row-label" scope="row">{t('dashboard.tableTotal')}</th>
          {#each entityNames as entity (entity)}
            <td class="num total-col" title={totalTitle(entityTotals.get(entity))}>
              <span class="amount">{amountText(entityTotals.get(entity))}</span>
              <span class="share">{shareText(entityTotals.get(entity))}</span>
            </td>
          {/each}
          {#if entityNames.length > 1}
            <td class="num grand-total">
              <span class="amount">{amountText(grandTotal)}</span>
            </td>
          {/if}
        </tr>
      </tfoot>
    </table>
  </div>

  {#if missingCurrencies.length > 0}
    <p class="warning">* {t('dashboard.rateMissingNote', { currencies: missingCurrencies.join(', ') })}</p>
  {/if}

  <div class="legend">
    <span class="legend-title">{t('dashboard.shareOfPortfolio')}</span>
    {#each LEGEND as step (step.key)}
      <span class="swatch {step.cls}"></span>
      <span class="legend-label">{t(step.key)}</span>
    {/each}
  </div>
</div>

<style>
  .matrix {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .matrix-scroll {
    overflow-x: auto;
  }

  .matrix-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
    font-variant-numeric: tabular-nums;
  }

  th,
  td {
    padding: var(--space-2) var(--space-3);
    text-align: right;
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  th {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
  }

  .corner {
    text-align: left;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .row-label {
    position: sticky;
    left: 0;
    z-index: 1;
    text-align: left;
    color: var(--color-text-primary);
    background: var(--color-surface);
  }

  thead .row-label {
    background: var(--color-surface-alt);
  }

  tbody tr:hover td {
    box-shadow: inset 0 0 0 999px rgba(0, 0, 0, 0.03);
  }

  tbody tr:hover .row-label {
    background: var(--color-surface-hover);
  }

  .num {
    vertical-align: middle;
  }

  .amount {
    display: block;
    line-height: 1.2;
    color: var(--color-text-primary);
  }

  .share {
    display: block;
    line-height: 1.1;
    font-size: var(--font-size-xs);
    color: var(--color-text-primary);
  }

  .dash {
    color: var(--color-text-muted);
  }

  .flag {
    color: inherit;
    font-weight: var(--font-weight-semibold);
    margin-left: 2px;
  }

  .total-col {
    font-weight: var(--font-weight-semibold);
  }

  tfoot .row-label,
  tfoot td {
    border-top: 2px solid var(--color-border);
    background: var(--color-surface-hover);
  }

  .grand-total .amount {
    font-weight: var(--font-weight-bold);
  }

  .heat-1 { background: color-mix(in srgb, var(--color-primary) 8%, var(--color-surface)); }
  .heat-2 { background: color-mix(in srgb, var(--color-primary) 16%, var(--color-surface)); }
  .heat-3 { background: color-mix(in srgb, var(--color-primary) 28%, var(--color-surface)); }
  .heat-4 { background: color-mix(in srgb, var(--color-primary) 42%, var(--color-surface)); }
  .heat-5 { background: color-mix(in srgb, var(--color-primary) 56%, var(--color-surface)); }

  .warning {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-warning);
  }

  .legend {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .legend-title {
    color: var(--color-text-muted);
  }

  .swatch {
    width: 18px;
    height: 10px;
    border: 1px solid var(--color-border);
    border-radius: 2px;
  }

  .legend-label {
    margin-right: var(--space-2);
  }
</style>
