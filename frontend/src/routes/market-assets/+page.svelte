<script>
  import { onMount } from 'svelte';
  import { crud } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import Select from '$lib/components/Select.svelte';
  import AddMarketAssetModal from '$lib/components/modals/AddMarketAssetModal.svelte';
  import EditMarketAssetModal from '$lib/components/modals/EditMarketAssetModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import { t } from '$lib/i18n/index.svelte';

  let loading = $state(true);
  let error = $state(null);
  let assets = $state([]);
  let searchQuery = $state('');
  let typeFilter = $state('all');
  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 20;

  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingAsset = $state(null);
  let deletingAsset = $state(null);

  let TYPE_FILTERS = $derived([
    { value: 'all', label: t('common.allTypes') },
    { value: 'STOCK', label: t('marketAssets.filterStock') },
    { value: 'ETF', label: t('marketAssets.filterETF') },
    { value: 'ETC', label: t('marketAssets.filterETC') },
    { value: 'FUND', label: t('marketAssets.filterFund') },
    { value: 'INDEX FUND', label: t('marketAssets.filterIndexFund') },
    { value: 'CRYPTO', label: t('marketAssets.filterCrypto') },
    { value: 'OTHER', label: t('marketAssets.filterOther') },
  ]);

  let filteredAssets = $derived(
    assets.filter(a => {
      const matchesSearch = !searchQuery ||
        (a.market_code && a.market_code.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (a.name && a.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (a.ticker && a.ticker.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesType = typeFilter === 'all' || a.asset_type === typeFilter;
      return matchesSearch && matchesType;
    })
  );

  let totalPages = $derived(Math.ceil(filteredAssets.length / ITEMS_PER_PAGE));
  let paginatedAssets = $derived(
    filteredAssets.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
  );

  $effect(() => {
    searchQuery;
    typeFilter;
    currentPage = 1;
  });

  function getTypeBadgeClass(type) {
    const map = {
      'STOCK': 'badge-primary',
      'ETF': 'badge-info',
      'ETC': 'badge-warning',
      'FUND': 'badge-success',
      'INDEX FUND': 'badge-success',
      'CRYPTO': 'badge-danger',
      'OTHER': 'badge-default',
    };
    return map[type] || 'badge-default';
  }

  async function loadAssets() {
    loading = true;
    error = null;
    try {
      assets = await crud.marketAssets.getList();
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'market assets' });
    } finally {
      loading = false;
    }
  }

  function handleEdit(asset) {
    editingAsset = asset;
    editModalOpen = true;
  }

  function handleDelete(asset) {
    deletingAsset = asset;
    deleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!deletingAsset) return;
    try {
      await crud.marketAssets.remove(deletingAsset.market_code);
      deleteModalOpen = false;
      deletingAsset = null;
      await loadAssets();
    } catch (e) {
      error = e.message || 'Failed to delete market asset';
      deleteModalOpen = false;
      deletingAsset = null;
    }
  }

  onMount(loadAssets);
</script>

<div class="page-header">
  <h1 class="page-title">{t('marketAssets.title')}</h1>
  <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('marketAssets.add')}</Button>
</div>

{#if loading}
  <LoadingSpinner message={t('marketAssets.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAssets}>{t('common.retry')}</Button>
  </div>
{:else if assets.length === 0}
  <EmptyState title={t('marketAssets.emptyTitle')} message={t('marketAssets.emptyMsg')} />
{:else}
  <div class="filter-bar">
    <div class="filter-group">
      <TextInput bind:value={searchQuery} placeholder={t('common.search')} />
    </div>
    <div class="filter-group">
      <Select
        value={typeFilter}
        options={TYPE_FILTERS}
        onchange={(e) => typeFilter = e.target.value}
      />
    </div>
    <div class="filter-info">
      {filteredAssets.length} asset{filteredAssets.length !== 1 ? 's' : ''}
    </div>
  </div>

  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>{t('marketAssets.marketCode')}</th>
          <th>{t('common.name')}</th>
          <th>{t('common.type')}</th>
          <th>Class</th>
          <th>{t('common.currency')}</th>
          <th>{t('marketAssets.exchange')}</th>
          <th class="actions-th">{t('common.actions')}</th>
        </tr>
      </thead>
      <tbody>
        {#each paginatedAssets as asset (asset.market_code)}
          <tr>
            <td class="cell-code">{asset.market_code}</td>
            <td class="cell-name">{asset.name || '-'}</td>
            <td><span class="badge {getTypeBadgeClass(asset.asset_type)}">{asset.asset_type}</span></td>
            <td>{asset.asset_class || '-'}</td>
            <td>{asset.currency_code}</td>
            <td>{asset.exchange || '-'}</td>
            <td class="actions-cell">
              <button class="icon-btn" title="Edit" aria-label="Edit asset" onclick={() => handleEdit(asset)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button class="icon-btn icon-btn-danger" title="Delete" aria-label="Delete asset" onclick={() => handleDelete(asset)}>
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

  {#if totalPages > 1}
    <Pagination
      totalItems={filteredAssets.length}
      itemsPerPage={ITEMS_PER_PAGE}
      bind:currentPage={currentPage}
    />
  {/if}
{/if}

<AddMarketAssetModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAssets} />
<EditMarketAssetModal open={editModalOpen} asset={editingAsset} onclose={() => { editModalOpen = false; editingAsset = null; }} onsuccess={loadAssets} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingAsset = null; }}
  onconfirm={confirmDelete}
  title={t('marketAssets.deleteTitle')}
  entityName={deletingAsset ? `${deletingAsset.market_code} — ${deletingAsset.name || ''}` : ''}
  message={t('marketAssets.deleteMsg')}
/>

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

  .filter-bar {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .filter-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin-left: auto;
  }

  .table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .data-table th {
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

  .data-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .data-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .actions-th {
    text-align: center;
    width: 80px;
  }

  .actions-cell {
    text-align: center;
  }

  .cell-code {
    font-family: var(--font-mono);
    font-weight: var(--font-weight-medium);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
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

  .badge-success {
    background: rgba(47, 158, 68, 0.1);
    color: var(--color-success);
  }

  .badge-danger {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .badge-default {
    background: var(--color-surface-hover);
    color: var(--color-text-secondary);
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
