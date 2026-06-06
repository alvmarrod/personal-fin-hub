<script>
  import { onMount } from 'svelte';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';

  // Loading states
  let loading = $state(true);
  let error = $state(null);

  // Data
  let transactions = $state([]);
  let entities = $state([]);
  let currencies = $state([]);
  let portfolioAssets = $state([]);

  // Reactive maps
  let entityMap = $state({});
  let currencyMap = $state({});
  let assetMap = $state({});

  // Filters
  let timePreset = $state('6m');
  let typeFilter = $state('all');
  let entityFilter = $state('all');
  let currencyFilter = $state('all');
  let customStart = $state('');
  let customEnd = $state('');

  // Pagination
  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 20;

  // Modals
  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingTransaction = $state(null);
  let deletingTransaction = $state(null);

  // Filter options
  const TIME_PRESETS = [
    { key: '3m', label: '3 months' },
    { key: '6m', label: '6 months' },
    { key: '1y', label: '1 year' },
    { key: 'all', label: 'All' },
    { key: 'custom', label: 'Custom' },
  ];

  const TYPE_FILTERS = [
    { key: 'all', label: 'All Types' },
    { key: 'income', label: 'Income', types: ['MONEY_IN', 'INTEREST', 'DIVIDEND'] },
    { key: 'expense', label: 'Expenses', types: ['MONEY_OUT'] },
    { key: 'investment', label: 'Investment', types: ['INVESTMENT_BUY', 'INVESTMENT_SELL'] },
  ];

  // Helper functions
  function today() { return new Date(); }
  
  function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
  }
  
  function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function getTimeRange(preset, customStart, customEnd) {
    if (preset === 'custom') {
      return { start: customStart || null, end: customEnd || null };
    }
    const now = today();
    switch (preset) {
      case '3m': return { start: formatDate(addMonths(now, -3)), end: formatDate(now) };
      case '6m': return { start: formatDate(addMonths(now, -3)), end: formatDate(addMonths(now, 3)) };
      case '1y': return { start: formatDate(addMonths(now, -12)), end: formatDate(now) };
      case 'all': return { start: null, end: null };
      default: return { start: formatDate(addMonths(now, -3)), end: formatDate(addMonths(now, 3)) };
    }
  }

  function formatType(type) {
    const labels = {
      'MONEY_IN': 'Income',
      'MONEY_OUT': 'Expense',
      'INVESTMENT_BUY': 'Buy',
      'INVESTMENT_SELL': 'Sell',
      'DIVIDEND': 'Dividend',
      'INTEREST': 'Interest',
    };
    return labels[type] || type;
  }

  function getTypeBadgeVariant(type) {
    const variants = {
      'MONEY_IN': 'success',
      'MONEY_OUT': 'danger',
      'INVESTMENT_BUY': 'primary',
      'INVESTMENT_SELL': 'info',
      'DIVIDEND': 'warning',
      'INTEREST': 'success',
    };
    return variants[type] || 'default';
  }

  function truncate(str, len) {
    if (!str) return '-';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  // Data loading
  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [txList, entityList, currencyList, assetList] = await Promise.all([
        crud.transactions.getList(),
        crud.entities.getList(),
        currenciesApi.getList(),
        crud.portfolioAssets.getList(),
      ]);
      
      transactions = txList;
      entities = entityList;
      currencies = currencyList;
      portfolioAssets = assetList;
      
      // Build lookup maps
      entityMap = {};
      for (const e of entities) entityMap[e.id] = e.name;
      
      currencyMap = {};
      for (const c of currencies) currencyMap[c] = c;
      
      assetMap = {};
      for (const a of portfolioAssets) assetMap[a.id] = a;
      
    } catch (e) {
      error = e.message || 'Failed to load transactions';
    } finally {
      loading = false;
    }
  }

  // Filter handlers
  function selectTimePreset(key) {
    timePreset = key;
    currentPage = 1;
  }

  // Computed properties
  let filteredTransactions = $derived(() => {
    let result = transactions;
    
    // Time filter
    const range = getTimeRange(timePreset, customStart, customEnd);
    if (range.start && range.end) {
      result = result.filter(tx => {
        const txDate = new Date(tx.timestamp);
        return txDate >= new Date(range.start) && txDate <= new Date(range.end + 'T23:59:59');
      });
    }
    
    // Type filter
    if (typeFilter !== 'all') {
      const typeConfig = TYPE_FILTERS.find(f => f.key === typeFilter);
      if (typeConfig?.types) {
        result = result.filter(tx => typeConfig.types.includes(tx.type));
      }
    }
    
    // Entity filter
    if (entityFilter !== 'all') {
      result = result.filter(tx => tx.entity_id === parseInt(entityFilter));
    }
    
    // Currency filter
    if (currencyFilter !== 'all') {
      result = result.filter(tx => tx.currency === currencyFilter);
    }
    
    return result;
  });

  let paginatedTransactions = $derived(
    filteredTransactions.slice(
      (currentPage - 1) * ITEMS_PER_PAGE,
      currentPage * ITEMS_PER_PAGE
    )
  );

  // Reset pagination when filters change
  $effect(() => {
    currentPage = 1;
  });

  // Action handlers
  function handleEdit(tx) {
    editingTransaction = tx;
    editModalOpen = true;
  }

  function handleDelete(tx) {
    deletingTransaction = tx;
    deleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!deletingTransaction) return;
    try {
      await crud.transactions.remove(deletingTransaction.id);
      deleteModalOpen = false;
      deletingTransaction = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete transaction';
      deleteModalOpen = false;
      deletingTransaction = null;
    }
  }

  onMount(loadAll);
</script>

<div class="page-header">
  <h1 class="page-title">Transactions</h1>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>+ Add Transaction</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message="Loading transactions..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if transactions.length === 0}
  <EmptyState title="No transactions yet" message="Add your first transaction to get started." />
{:else}
  <!-- Filter Bar -->
  <div class="filter-bar">
    <div class="filter-section">
      {#each TIME_PRESETS as p (p.key)}
        <button
          class="preset-btn"
          class:active={timePreset === p.key}
          onclick={() => selectTimePreset(p.key)}
        >{p.label}</button>
      {/each}
      {#if timePreset === 'custom'}
        <div class="custom-dates">
          <label>
            From
            <input type="date" bind:value={customStart} onchange={() => currentPage = 1} />
          </label>
          <label>
            To
            <input type="date" bind:value={customEnd} onchange={() => currentPage = 1} />
          </label>
        </div>
      {/if}
    </div>
    
    <div class="filter-section">
      {#each TYPE_FILTERS as f (f.key)}
        <button
          class="filter-btn"
          class:active={typeFilter === f.key}
          onclick={() => typeFilter = f.key}
        >{f.label}</button>
      {/each}
    </div>
    
    <div class="filter-section">
      <div class="control-group">
        <span class="control-label">Entity:</span>
        <Select
          value={entityFilter}
          options={[{value: 'all', label: 'All Entities'}, ...entities.map(e => ({value: e.id, label: e.name}))]}
          onchange={(e) => entityFilter = e.target.value}
        />
      </div>
    </div>
    
    <div class="filter-section">
      <div class="control-group">
        <span class="control-label">Currency:</span>
        <Select
          value={currencyFilter}
          options={[{value: 'all', label: 'All Currencies'}, ...currencies.map(c => ({value: c, label: c}))]}
          onchange={(e) => currencyFilter = e.target.value}
        />
      </div>
    </div>
  </div>

  <!-- Transactions Table -->
  <div class="table-section">
    <div class="table-wrap">
      <table class="transactions-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Entity</th>
            <th class="num">Amount</th>
            <th>Currency</th>
            <th>Category</th>
            <th>Notes</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedTransactions as tx (tx.id)}
            <tr>
              <td>{new Date(tx.timestamp).toLocaleDateString()}</td>
              <td>
                <span class="badge badge-{getTypeBadgeVariant(tx.type)}">
                  {formatType(tx.type)}
                </span>
              </td>
              <td>{entityMap[tx.entity_id] || tx.entity_id}</td>
              <td class="num">{tx.total_value?.toLocaleString() || '-'}</td>
              <td><span class="badge badge-info">{tx.currency}</span></td>
              <td>
                {#if tx.transaction_category}
                  <span class="badge badge-warning">{tx.transaction_category}</span>
                {:else}
                  <span class="text-muted">-</span>
                {/if}
              </td>
              <td class="cell-notes" title={tx.notes}>{truncate(tx.notes, 50)}</td>
              <td class="actions-cell">
                <button class="icon-btn" title="Edit" onclick={(e) => { e.stopPropagation(); handleEdit(tx); }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                </button>
                <button class="icon-btn icon-btn-danger" title="Delete" onclick={(e) => { e.stopPropagation(); handleDelete(tx); }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination
      totalItems={filteredTransactions.length}
      itemsPerPage={ITEMS_PER_PAGE}
      bind:currentPage={currentPage}
    />
  </div>
{/if}

<!-- Modals will be added in Phase 3 -->

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .filter-bar {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
    padding: var(--space-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .filter-section {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .preset-btn, .filter-btn {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
    cursor: pointer;
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
  }

  .preset-btn:hover, .filter-btn:hover {
    background: var(--color-surface-hover);
    border-color: var(--color-primary);
  }

  .preset-btn.active, .filter-btn.active {
    background: var(--color-primary);
    color: var(--color-text-on-primary);
    border-color: var(--color-primary);
  }

  .custom-dates {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-left: var(--space-2);
  }

  .custom-dates label {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .custom-dates input[type="date"] {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .control-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .control-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-medium);
  }

  .table-section {
    margin-bottom: var(--space-6);
  }

  .table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .transactions-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .transactions-table th {
    padding: var(--space-3) var(--space-4);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
    position: sticky;
    top: 0;
  }

  .transactions-table th.num {
    text-align: right;
  }

  .transactions-table th.actions-col {
    width: 80px;
    text-align: center;
  }

  .transactions-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-muted);
  }

  .badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .badge-success {
    background: rgba(47, 158, 68, 0.1);
    color: var(--color-success);
  }

  .badge-danger {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .badge-primary {
    background: rgba(66, 99, 235, 0.1);
    color: var(--color-primary);
  }

  .badge-info {
    background: rgba(25, 113, 194, 0.1);
    color: var(--color-info);
  }

  .badge-warning {
    background: rgba(240, 140, 0, 0.1);
    color: var(--color-warning);
  }

  .badge-default {
    background: var(--color-surface-hover);
    color: var(--color-text-secondary);
  }

  .text-muted {
    color: var(--color-text-muted);
  }

  .actions-cell {
    text-align: center;
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .error-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    text-align: center;
  }

  .error-message {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
  }
</style>
