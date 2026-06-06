<script>
  let { totalItems, itemsPerPage = 10, currentPage = $bindable(1) } = $props();

  const totalPages = $derived(Math.ceil(totalItems / itemsPerPage));
  const startItem = $derived((currentPage - 1) * itemsPerPage + 1);
  const endItem = $derived(Math.min(currentPage * itemsPerPage, totalItems));

  function goToPage(page) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
    }
  }

  function goToFirst() {
    goToPage(1);
  }

  function goToPrevious() {
    goToPage(currentPage - 1);
  }

  function goToNext() {
    goToPage(currentPage + 1);
  }

  function goToLast() {
    goToPage(totalPages);
  }

  function handlePageSelect(event) {
    const page = parseInt(event.target.value);
    goToPage(page);
  }

  // Generate page numbers for dropdown
  const pageOptions = $derived(
    Array.from({ length: totalPages }, (_, i) => ({
      value: i + 1,
      label: `Página ${i + 1}`
    }))
  );
</script>

{#if totalItems > 0}
  <div class="pagination">
    <div class="pagination-info">
      Mostrando {startItem}-{endItem} de {totalItems}
    </div>

    <div class="pagination-controls">
      <button
        class="pagination-btn"
        onclick={goToFirst}
        disabled={currentPage === 1}
        aria-label="Primera página"
      >
        «
      </button>

      <button
        class="pagination-btn"
        onclick={goToPrevious}
        disabled={currentPage === 1}
        aria-label="Página anterior"
      >
        ‹
      </button>

      <select
        class="pagination-select"
        value={currentPage}
        onchange={handlePageSelect}
        aria-label="Seleccionar página"
      >
        {#each pageOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>

      <button
        class="pagination-btn"
        onclick={goToNext}
        disabled={currentPage === totalPages}
        aria-label="Página siguiente"
      >
        ›
      </button>

      <button
        class="pagination-btn"
        onclick={goToLast}
        disabled={currentPage === totalPages}
        aria-label="Última página"
      >
        »
      </button>
    </div>
  </div>
{/if}

<style>
  .pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3) 0;
    gap: var(--space-3);
  }

  .pagination-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .pagination-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .pagination-btn {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    cursor: pointer;
    transition: all var(--transition-fast);
    min-width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pagination-btn:hover:not(:disabled) {
    background: var(--color-surface-hover);
    border-color: var(--color-primary);
  }

  .pagination-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pagination-select {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    cursor: pointer;
    height: 32px;
    min-width: 120px;
  }

  .pagination-select:hover {
    border-color: var(--color-primary);
  }

  .pagination-select:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px var(--color-primary-alpha);
  }
</style>
