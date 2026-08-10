<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { t } from '$lib/i18n/index.svelte';
  import { crud, currenciesApi } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import AddTransactionModal from '$lib/components/modals/AddTransactionModal.svelte';
  import EditTransactionModal from '$lib/components/modals/EditTransactionModal.svelte';
  import DetailTransactionModal from '$lib/components/modals/DetailTransactionModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { transactions as transactionsTutorial } from '$lib/tutorial/definitions/index';
  import transactionsMock from '$lib/tutorial/mocks/transactions';

  tutorialStore.registerMock('transactions', transactionsMock);

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
  let assetNameMap = $state({});

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
  let detailModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingTransaction = $state(null);
  let viewingTransaction = $state(null);
  let deletingTransaction = $state(null);

  // Filter options
  let TIME_PRESETS = $derived([
    { key: '3m', label: t('common.preset3m') },
    { key: '6m', label: t('common.preset6m') },
    { key: '1y', label: t('common.preset1y') },
    { key: 'all', label: t('common.presetAll') },
    { key: 'custom', label: t('common.custom') },
  ]);

  let TYPE_FILTERS = $derived([
    { key: 'all', label: t('common.allTypes') },
    { key: 'income', label: t('transactions.typeIncome'), types: ['MONEY_IN', 'INTEREST', 'DIVIDEND'] },
    { key: 'expense', label: t('transactions.typeExpense'), types: ['MONEY_OUT'] },
    { key: 'investment', label: t('transactions.typeInvestment'), types: ['INVESTMENT_BUY', 'INVESTMENT_SELL'] },
    { key: 'transfer', label: t('transactions.typeTransfer'), types: ['TRANSFER_IN', 'TRANSFER_OUT'] },
  ]);

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
      'MONEY_IN': t('transactions.typeIncome'),
      'MONEY_OUT': t('transactions.typeExpense'),
      'INVESTMENT_BUY': t('transactions.typeBuy'),
      'INVESTMENT_SELL': t('transactions.typeSell'),
      'DIVIDEND': t('transactions.typeDividend'),
      'INTEREST': t('transactions.typeInterest'),
      'TRANSFER': t('transactions.typeTransfer'),
      'TRANSFER_IN': t('transactions.typeTransferIn'),
      'TRANSFER_OUT': t('transactions.typeTransferOut'),
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
      'TRANSFER': 'default',
      'TRANSFER_IN': 'default',
      'TRANSFER_OUT': 'default',
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
      const [txList, entityList, currencyList, assetList, marketList] = await Promise.all([
        crud.transactions.getList(),
        crud.entities.getList(),
        currenciesApi.getList(),
        crud.portfolioAssets.getList(),
        crud.marketAssets.getList(),
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

      const marketMap = {};
      for (const m of (marketList || [])) marketMap[m.market_code] = m;

      assetNameMap = {};
      for (const a of portfolioAssets) {
        const ma = marketMap[a.market_code];
        assetNameMap[a.id] = ma ? (ma.name || ma.ticker || a.market_code) : a.market_code;
      }

    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'transactions' });
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
  let filteredTransactions = $derived.by(() => {
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
  function handleView(tx) {
    viewingTransaction = tx;
    detailModalOpen = true;
  }

  function handleEdit(tx) {
    editingTransaction = tx;
    editModalOpen = true;
  }

  function handleDelete(tx) {
    deletingTransaction = tx;
    deleteModalOpen = true;
  }

  function handleEditFromDetail(tx) {
    detailModalOpen = false;
    editingTransaction = tx;
    editModalOpen = true;
  }

  function handleDeleteFromDetail(tx) {
    detailModalOpen = false;
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
      error = e.message || t('common.errorPrefix', { resource: 'transactions' });
      deleteModalOpen = false;
      deletingTransaction = null;
    }
  }

  onMount(() => {
    const params = $page.url.searchParams;
    if (params.get('type')) {
      const rawType = params.get('type');
      const group = TYPE_FILTERS.find(f => f.types?.includes(rawType));
      typeFilter = group ? group.key : rawType;
    }
    if (params.get('entity')) entityFilter = params.get('entity');
    if (params.get('currency')) currencyFilter = params.get('currency');
    if (params.get('period')) {
      timePreset = 'custom';
      customStart = params.get('period') + '-01';
      const d = new Date(customStart);
      d.setMonth(d.getMonth() + 1);
      customEnd = formatDate(new Date(d.getTime() - 86400000));
    }
    loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('transactions'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('transactions');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('transactions.title')}</h1>
    <ReplayButton page="transactions" />
  </div>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('transactions.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('transactions.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if transactions.length === 0}
  <EmptyState title={t('transactions.emptyTitle')} message={t('transactions.emptyMsg')} />
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
            {t('common.from')}
            <input type="date" bind:value={customStart} onchange={() => currentPage = 1} />
          </label>
          <label>
            {t('common.to')}
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
        <span class="control-label">{t('transactions.filterEntity')}:</span>
        <Select
          value={entityFilter}
          options={[{value: 'all', label: t('common.allEntities')}, ...entities.map(e => ({value: e.id, label: e.name}))]}
          onchange={(e) => entityFilter = e.target.value}
        />
      </div>
    </div>

    <div class="filter-section">
      <div class="control-group">
        <span class="control-label">{t('transactions.filterCurrency')}:</span>
        <Select
          value={currencyFilter}
          options={[{value: 'all', label: t('common.allCurrencies')}, ...currencies.map(c => ({value: c, label: c}))]}
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
            <th>{t('common.date')}</th>
            <th>{t('common.type')}</th>
            <th>{t('common.entity')}</th>
            <th class="num">{t('common.amount')}</th>
            <th>{t('common.currency')}</th>
            <th>{t('transactions.asset')}</th>
            <th>{t('transactions.category')}</th>
            <th>{t('common.notes')}</th>
            <th class="actions-col">{t('common.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedTransactions as tx (tx.id)}
            <tr class="clickable-row" onclick={() => handleView(tx)} onkeydown={(e) => e.key === 'Enter' && handleView(tx)} tabindex="0" role="button" aria-label={t('transactions.viewAria', { id: tx.id })}>
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
                {#if tx.portfolio_asset_id}
                  {assetNameMap[tx.portfolio_asset_id] || tx.portfolio_asset_id}
                {:else}
                  <span class="text-muted">{t('transactions.cash')}</span>
                {/if}
              </td>
              <td>
                {#if tx.transaction_category}
                  <span class="badge badge-warning">{tx.transaction_category}</span>
                {:else}
                  <span class="text-muted">-</span>
                {/if}
              </td>
              <td class="cell-notes" title={tx.notes}>{truncate(tx.notes, 50)}</td>
              <td class="actions-cell" onclick={(e) => e.stopPropagation()}>
                <button class="icon-btn" title="Edit" aria-label={t('transactions.editAria')} onclick={() => handleEdit(tx)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                </button>
                <button class="icon-btn icon-btn-danger" title="Delete" aria-label={t('transactions.deleteAria')} onclick={() => handleDelete(tx)}>
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

<!-- Modals -->
<AddTransactionModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditTransactionModal open={editModalOpen} transaction={editingTransaction} onclose={() => { editModalOpen = false; editingTransaction = null; }} onsuccess={loadAll} />
<DetailTransactionModal open={detailModalOpen} transaction={viewingTransaction} onclose={() => { detailModalOpen = false; viewingTransaction = null; }} onedit={handleEditFromDetail} ondelete={handleDeleteFromDetail} {assetNameMap} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingTransaction = null; }}
  onconfirm={confirmDelete}
  title={t('transactions.deleteTitle')}
  entityName={deletingTransaction ? `${formatType(deletingTransaction.type)} - ${deletingTransaction.total_value}` : ''}
  message={t('transactions.deleteMsg')}
/>

<TutorialOverlay definition={transactionsTutorial} page="transactions" onfinish={loadAll} />

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

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .filter-bar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
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
    padding-right: var(--space-3);
    border-right: 1px solid var(--color-border);
  }

  .filter-section:last-child {
    border-right: none;
    padding-right: 0;
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

  .clickable-row {
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .clickable-row:hover {
    background: var(--color-surface-hover);
  }

  .clickable-row:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: -2px;
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

  @media (max-width: 768px) {
    .filter-bar {
      flex-direction: column;
      align-items: stretch;
    }

    .filter-section {
      width: 100%;
    }

    .control-group {
      width: 100%;
    }

    .control-group select {
      flex: 1;
    }
  }
</style>
