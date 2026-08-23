<script>
  import { t } from '$lib/i18n/index.svelte';

  let { col, sorter } = $props();
</script>

<th
  class="sortable-th"
  class:num={col.align === 'right'}
  class:sort-active={sorter.sortKey === col.key}
  onclick={() => sorter.toggle(col.key)}
>
  {t(col.labelKey)}
  <span class="sort-indicator">{sorter.sortKey === col.key ? (sorter.sortDir === 'asc' ? '▲' : '▼') : ''}</span>
</th>

<style>
  .sortable-th {
    cursor: pointer;
    user-select: none;
  }

  .sortable-th:hover {
    color: var(--color-primary);
  }

  .sort-indicator {
    font-size: 10px;
    color: var(--color-primary);
    margin-left: 4px;
  }
</style>
