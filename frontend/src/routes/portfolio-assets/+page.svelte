<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client.js';
  import { crud } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import Select from '$lib/components/Select.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import AddPortfolioAssetModal from '$lib/components/modals/AddPortfolioAssetModal.svelte';
  import EditPortfolioAssetModal from '$lib/components/modals/EditPortfolioAssetModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';

  let loading = $state(true);
  let error = $state(null);
  let portfolioAssets = $state([]);
  let marketAssets = $state([]);
  let searchQuery = $state('');
  let layerFilter = $state('all');
  let statusFilter = $state('all');
  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 20;

  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let deleteModalOpen = $state(false);
  let editingAsset = $state(null);
  let deletingAsset = $state(null);

  let syncing = $state(false);
  let selectedAsset = $state(null);
  let priceData = $state({ labels: [], values: [] });
  let priceLoading = $state(false);

  const LAYER_FILTERS = [
    { value: 'all', label: 'All Layers' },
    { value: 'core', label: 'Core' },
    { value: 'reserve', label: 'Reserve' },
    { value: 'satellite', label: 'Satellite' },
  ];

  const STATUS_FILTERS = [
    { value: 'all', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ];

  let marketAssetMap = $state({});

  let enrichedAssets = $derived(
    portfolioAssets.map(pa => ({
      ...pa,
      marketAsset: marketAssetMap[pa.market_code] || null,
      displayName: marketAssetMap[pa.market_code]?.name || pa.market_code,
      displayType: marketAssetMap[pa.market_code]?.asset_type || '-',
      displayCurrency: marketAssetMap[pa.market_code]?.currency_code || '-',
    }))
  );

  let filteredAssets = $derived(
    enrichedAssets.filter(a => {
      const matchesSearch = !searchQuery ||
        (a.market_code && a.market_code.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (a.displayName && a.displayName.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesLayer = layerFilter === 'all' || a.layer === layerFilter;
      const matchesStatus = statusFilter === 'all' ||
        (statusFilter === 'active' && a.is_active) ||
        (statusFilter === 'inactive' && !a.is_active);
      return matchesSearch && matchesLayer && matchesStatus;
    })
  );

  let totalPages = $derived(Math.ceil(filteredAssets.length / ITEMS_PER_PAGE));
  let paginatedAssets = $derived(
    filteredAssets.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
  );

  $effect(() => {
    searchQuery;
    layerFilter;
    statusFilter;
    currentPage = 1;
  });

  function getLayerBadgeClass(layer) {
    const map = {
      'core': 'badge-primary',
      'reserve': 'badge-info',
      'satellite': 'badge-warning',
    };
    return map[layer] || 'badge-default';
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [paList, maList] = await Promise.all([
        crud.portfolioAssets.getList(),
        crud.marketAssets.getList(),
      ]);
      portfolioAssets = paList;
      marketAssets = maList;
      marketAssetMap = {};
      for (const ma of maList) {
        marketAssetMap[ma.market_code] = ma;
      }
    } catch (e) {
      error = e.message || 'Failed to load portfolio assets';
    } finally {
      loading = false;
    }
  }

  async function handleSyncPrices() {
    syncing = true;
    error = null;
    try {
      await api.post('/market/sync-prices');
      if (selectedAsset) await loadPriceHistory(selectedAsset.market_code);
    } catch (e) {
      error = e.message || 'Sync failed';
    } finally {
      syncing = false;
    }
  }

  async function handleRowClick(asset) {
    if (selectedAsset?.id === asset.id) {
      selectedAsset = null;
      priceData = { labels: [], values: [] };
      return;
    }
    selectedAsset = asset;
    await loadPriceHistory(asset.market_code);
  }

  async function loadPriceHistory(marketCode) {
    priceLoading = true;
    try {
      const points = await api.get(`/prices/chart/${encodeURIComponent(marketCode)}`);
      priceData = {
        labels: (points || []).map(p => p.date),
        values: (points || []).map(p => p.price),
      };
    } catch {
      priceData = { labels: [], values: [] };
    } finally {
      priceLoading = false;
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
      await crud.portfolioAssets.remove(deletingAsset.id);
      deleteModalOpen = false;
      deletingAsset = null;
      await loadAll();
    } catch (e) {
      error = e.message || 'Failed to delete portfolio asset';
      deleteModalOpen = false;
      deletingAsset = null;
    }
  }

  onMount(loadAll);
</script>

<div class="page-header">
  <h1 class="page-title">Portfolio Assets</h1>
  <div class="page-actions">
    <Button variant="secondary" size="sm" onclick={handleSyncPrices} disabled={syncing}>
      {syncing ? 'Syncing...' : 'Sync Prices'}
    </Button>
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>+ Add Portfolio Asset</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message="Loading portfolio assets..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if portfolioAssets.length === 0}
  <EmptyState title="No portfolio assets yet" message="Add your first portfolio asset to start tracking investments." />
{:else}
  <div class="filter-bar">
    <div class="filter-group">
      <TextInput bind:value={searchQuery} placeholder="Search by code or name..." />
    </div>
    <div class="filter-group">
      <Select
        value={layerFilter}
        options={LAYER_FILTERS}
        onchange={(e) => layerFilter = e.target.value}
      />
    </div>
    <div class="filter-group">
      <Select
        value={statusFilter}
        options={STATUS_FILTERS}
        onchange={(e) => statusFilter = e.target.value}
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
          <th>Market Code</th>
          <th>Name</th>
          <th>Type</th>
          <th>Currency</th>
          <th>Layer</th>
          <th>DCA</th>
          <th>Distribution</th>
          <th class="num">Desired %</th>
          <th class="num">TER</th>
          <th>Status</th>
          <th class="actions-th">Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each paginatedAssets as asset (asset.id)}
          <tr
            class="clickable-row"
            class:selected={selectedAsset?.id === asset.id}
            onclick={() => handleRowClick(asset)}
          >
            <td class="cell-code">{asset.market_code}</td>
            <td class="cell-name">{asset.displayName}</td>
            <td>{asset.displayType}</td>
            <td>{asset.displayCurrency}</td>
            <td>
              {#if asset.layer}
                <span class="badge {getLayerBadgeClass(asset.layer)}">{asset.layer}</span>
              {:else}
                -
              {/if}
            </td>
            <td>{asset.dca_status || '-'}</td>
            <td>{asset.distribution_type || '-'}</td>
            <td class="num">{asset.desired_weight != null ? `${asset.desired_weight}%` : '-'}</td>
            <td class="num">{asset.ter != null ? `${asset.ter}%` : '-'}</td>
            <td>
              <span class="badge {asset.is_active ? 'badge-success' : 'badge-default'}">
                {asset.is_active ? 'Active' : 'Closed'}
              </span>
            </td>
            <td class="actions-cell" onclick={(e) => e.stopPropagation()}>
              <button class="icon-btn" title="Edit" aria-label="Edit portfolio asset" onclick={() => handleEdit(asset)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button class="icon-btn icon-btn-danger" title="Delete" aria-label="Delete portfolio asset" onclick={() => handleDelete(asset)}>
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

  {#if selectedAsset}
    <div class="chart-section">
      <ChartCard title="Price History — {selectedAsset.market_code}">
        {#if priceLoading}
          <LoadingSpinner message="Loading prices..." />
        {:else if priceData.values.length > 0}
          <LineChart
            labels={priceData.labels}
            datasets={[{ data: priceData.values, label: selectedAsset.market_code }]}
            currencySymbol={selectedAsset.displayCurrency === 'USD' ? '$' : selectedAsset.displayCurrency === 'EUR' ? '€' : selectedAsset.displayCurrency === 'JPY' ? '¥' : selectedAsset.displayCurrency === 'GBP' ? '£' : ''}
          />
        {:else}
          <EmptyState title="No price data" message="Click 'Sync Prices' to fetch market data for this asset." />
        {/if}
      </ChartCard>
    </div>
  {/if}
{/if}

<AddPortfolioAssetModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditPortfolioAssetModal open={editModalOpen} asset={editingAsset} onclose={() => { editModalOpen = false; editingAsset = null; }} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingAsset = null; }}
  onconfirm={confirmDelete}
  title="Delete Portfolio Asset"
  entityName={deletingAsset ? `${deletingAsset.market_code}` : ''}
  message="This will permanently delete the portfolio asset. It cannot be deleted if it has transactions."
/>

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-actions {
    display: flex;
    gap: var(--space-3);
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
    border-bottom: 1px solid var(--color-border-light);
    vertical-align: middle;
  }

  .clickable-row {
    cursor: pointer;
  }

  .clickable-row:hover {
    background: var(--color-surface-hover);
  }

  .clickable-row.selected {
    background: var(--color-primary-light);
  }

  .cell-code { font-family: var(--font-mono); font-weight: var(--font-weight-semibold); }
  .cell-name { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .num { text-align: right; }
  .actions-th { width: 80px; text-align: center; }
  .actions-cell { display: flex; gap: var(--space-1); justify-content: center; }

  .chart-section { margin-top: var(--space-6); }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    text-transform: capitalize;
  }

  .badge-primary { background: var(--color-primary-light); color: var(--color-primary); }
  .badge-info { background: var(--color-info-light); color: var(--color-info); }
  .badge-warning { background: var(--color-warning-light); color: var(--color-warning); }
  .badge-success { background: var(--color-success-light); color: var(--color-success); }
  .badge-default { background: var(--color-surface-alt); color: var(--color-text-muted); }

  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: none;
    background: transparent;
    color: var(--color-text-secondary);
    cursor: pointer;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: var(--color-danger-light);
    color: var(--color-danger);
  }

  .error-card {
    background: var(--color-danger-light);
    border: 1px solid var(--color-danger-border);
    color: var(--color-danger);
    padding: var(--space-4);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .error-message { margin: 0; }
</style>
