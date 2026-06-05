<script>
  let { columns = [], rows = [], onRowClick, emptyMessage = 'No data' } = $props();
</script>

<div class="table-wrapper">
  <table class="data-table">
    <thead>
      <tr>
        {#each columns as col}
          <th class:align-right={col.align === 'right'} class:align-center={col.align === 'center'}>
            {col.label ?? col.key}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if rows.length === 0}
        <tr>
          <td colspan={columns.length} class="empty-cell">{emptyMessage}</td>
        </tr>
      {:else}
        {#each rows as row, i}
          <tr
            class:clickable={!!onRowClick}
            onclick={() => onRowClick?.(row, i)}
          >
            {#each columns as col}
              <td class:align-right={col.align === 'right'} class:align-center={col.align === 'center'}>
                {#if col.render}
                  {col.render(row)}
                {:else}
                  {row[col.key] ?? '-'}
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>

<style>
  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  thead {
    background: var(--color-surface-hover);
  }

  th {
    padding: var(--space-3) var(--space-4);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    font-size: var(--font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border-light);
    color: var(--color-text-primary);
  }

  tr:last-child td {
    border-bottom: none;
  }

  tbody tr:hover {
    background: var(--color-surface-hover);
  }

  tbody tr.clickable {
    cursor: pointer;
  }

  .align-right { text-align: right; }
  .align-center { text-align: center; }

  .empty-cell {
    text-align: center;
    color: var(--color-text-muted);
    padding: var(--space-8) var(--space-4);
    font-style: italic;
  }
</style>
