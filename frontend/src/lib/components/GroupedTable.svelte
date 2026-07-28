<script>
  import { t } from '$lib/i18n/index.svelte';

  let { rows = [], currencySymbol = '' } = $props();

  let assetClasses = $derived([...new Set(rows.map(r => r.assetClass).filter(Boolean))].sort());

  let subtotals = $derived(assetClasses.map(ac => {
    const classRows = rows.filter(r => r.assetClass === ac);
    return {
      assetClass: ac,
      origDetails: Object.entries(
        classRows.reduce((acc, r) => {
          acc[r.origCurrency] = (acc[r.origCurrency] || 0) + r.origAmount;
          return acc;
        }, {})
      ).map(([cur, sum]) =>
        `${sum.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`
      ).join(' + '),
      unifiedAmount: classRows.reduce((s, r) => s + r.unifiedAmount, 0),
    };
  }));

  let grandTotal = $derived(subtotals.reduce((s, st) => s + st.unifiedAmount, 0));

  function fmtUnified(v) {
    return `${currencySymbol}${(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
</script>

<div class="grouped-table">
  <table class="grouped-table-table">
    <thead>
      <tr>
        <th class="col-entity">{t('dashboard.entityCol')}</th>
        <th class="col-class">{t('dashboard.assetClassCol')}</th>
        <th class="col-orig">{t('dashboard.originalAmountCol')}</th>
        <th class="col-unified">{t('dashboard.unifiedAmountCol')}</th>
      </tr>
    </thead>
    <tbody>
      {#each assetClasses as ac}
        {#each rows.filter(r => r.assetClass === ac) as row, ri}
          <tr>
            <td class="cell-entity">{row.entity}</td>
            <td class="cell-class">{ri === 0 ? ac : ''}</td>
            <td class="num">{row.origAmount.toLocaleString(undefined, { maximumFractionDigits: 0 })} {row.origCurrency}</td>
            <td class="num">{fmtUnified(row.unifiedAmount)}</td>
          </tr>
        {/each}
        <tr class="subtotal-row">
          <td class="cell-entity">{t('dashboard.tableSubtotal')}</td>
          <td class="cell-class">{ac}</td>
          <td class="num">{subtotals.find(st => st.assetClass === ac).origDetails}</td>
          <td class="num">{fmtUnified(subtotals.find(st => st.assetClass === ac).unifiedAmount)}</td>
        </tr>
      {/each}
    </tbody>
    <tfoot>
      <tr class="total-row">
        <td class="cell-entity">{t('dashboard.tableTotal')}</td>
        <td></td>
        <td></td>
        <td class="num">{fmtUnified(grandTotal)}</td>
      </tr>
    </tfoot>
  </table>
</div>

<style>
  .grouped-table {
    overflow-x: auto;
  }

  .grouped-table-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  th, td {
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

  .col-entity, .col-class {
    text-align: left;
  }

  .col-orig, .col-unified {
    text-align: right;
  }

  .cell-entity, .cell-class {
    text-align: left;
    color: var(--color-text-primary);
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .subtotal-row td {
    border-top: 1px solid var(--color-border);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    background: var(--color-surface-alt);
  }

  .total-row td {
    border-top: 2px solid var(--color-border);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    background: var(--color-surface-hover);
  }
</style>
