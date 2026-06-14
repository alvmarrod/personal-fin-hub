<script>
  let { rows = [], columns = [], cellData, rowLabel = 'Asset Class', colLabel = 'Entity', currencySymbol = '' } = $props();

  let totalByRow = $derived(rows.map(r => columns.reduce((sum, c) => sum + (cellData(r, c) || 0), 0)));
  let totalByCol = $derived(columns.map(c => rows.reduce((sum, r) => sum + (cellData(r, c) || 0), 0)));
  let grandTotal = $derived(totalByRow.reduce((a, b) => a + b, 0));

  function fmt(v) {
    return `${currencySymbol}${(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
</script>

<div class="cross-tab">
  <table class="cross-tab-table">
    <thead>
      <tr>
        <th class="corner">{rowLabel} \ {colLabel}</th>
        {#each columns as col}
          <th>{col}</th>
        {/each}
        <th class="total-col">Total</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row, ri}
        <tr>
          <th class="row-label">{row}</th>
          {#each columns as col}
            <td>{fmt(cellData(row, col))}</td>
          {/each}
          <td class="total-col">{fmt(totalByRow[ri])}</td>
        </tr>
      {/each}
    </tbody>
    <tfoot>
      <tr>
        <th class="row-label">Total</th>
        {#each columns as col, ci}
          <td class="total-col">{fmt(totalByCol[ci])}</td>
        {/each}
        <td class="grand-total">{fmt(grandTotal)}</td>
      </tr>
    </tfoot>
  </table>
</div>

<style>
  .cross-tab {
    overflow-x: auto;
  }

  .cross-tab-table {
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

  .corner {
    text-align: left;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .row-label {
    text-align: left;
    color: var(--color-text-primary);
  }

  .total-col {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  .grand-total {
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    background: var(--color-surface-hover);
  }

  tbody tr:hover td {
    background: var(--color-surface-hover);
  }
</style>
