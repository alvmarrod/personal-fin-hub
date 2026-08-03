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
  import StackedAreaChart from '$lib/components/charts/StackedAreaChart.svelte';
  import AddPortfolioAssetModal from '$lib/components/modals/AddPortfolioAssetModal.svelte';
  import EditPortfolioAssetModal from '$lib/components/modals/EditPortfolioAssetModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { portfolioAssets as portfolioAssetsTutorial } from '$lib/tutorial/definitions/index';
  import portfolioAssetsMock from '$lib/tutorial/mocks/portfolio-assets';

  tutorialStore.registerMock('portfolio-assets', portfolioAssetsMock);
  if (!tutorialStore.isPageSeen('portfolio-assets')) {
    tutorialStore.start('portfolio-assets', portfolioAssetsTutorial);
  }

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
  let pricesLoading = $state(false);
  let flaggedSplits = $state([]);
  let confirmSplit = $state(null);
  let confirmingSplit = $state(false);
  let allPricesData = $state({ labels: [], datasets: [] });

  let currencyCodes = $state([]);
  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let pricePreset = $state('1y');
  let priceCustomStart = $state('');
  let priceCustomEnd = $state('');

  let PRICE_PRESETS = $derived([
    { value: '3m', label: t('common.presetShort3m') },
    { value: '6m', label: t('common.presetShort6m') },
    { value: '1y', label: t('common.presetShort1y') },
    { value: 'all', label: t('common.presetAll') },
    { value: 'custom', label: t('common.custom') },
  ]);

  function today() { return new Date(); }
  function addMonths(d, n) { const r = new Date(d); r.setMonth(r.getMonth() + n); return r; }
  function fmtDate(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

  function getPriceRange() {
    const now = today();
    switch (pricePreset) {
      case '3m': return `${fmtDate(addMonths(now, -3))}/${fmtDate(now)}`;
      case '6m': return `${fmtDate(addMonths(now, -6))}/${fmtDate(now)}`;
      case '1y': return `${fmtDate(addMonths(now, -12))}/${fmtDate(now)}`;
      case 'all': return '';
      case 'custom': {
        const s = priceCustomStart || fmtDate(addMonths(now, -12));
        const e = priceCustomEnd || fmtDate(now);
        return `${s}/${e}`;
      }
      default: return '';
    }
  }

  const CHART_COLORS = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'];

  let LAYER_FILTERS = $derived([
    { value: 'all', label: t('portfolioAssets.allLayers') },
    { value: 'core', label: t('portfolioAssets.core') },
    { value: 'reserve', label: t('portfolioAssets.reserve') },
    { value: 'satellite', label: t('portfolioAssets.satellite') },
  ]);

  let STATUS_FILTERS = $derived([
    { value: 'all', label: t('common.all') },
    { value: 'active', label: t('portfolioAssets.active') },
    { value: 'inactive', label: t('portfolioAssets.inactive') },
  ]);

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
      const [paList, maList, codes] = await Promise.all([
        api.get(`/portfolio-assets?display_currency=${_displayCurrency}`),
        crud.marketAssets.getList(),
        api.get('/currencies'),
      ]);
      portfolioAssets = paList;
      currencyCodes = codes;
      marketAssets = maList;
      marketAssetMap = {};
      for (const ma of maList) {
        marketAssetMap[ma.market_code] = ma;
      }
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'portfolio assets' });
    } finally {
      loading = false;
    }
    loadAllPrices();
  }

  async function loadAllPrices() {
    pricesLoading = true;
    try {
      const range = getPriceRange();
      const params = range ? `?start_date=${range.split('/')[0]}&end_date=${range.split('/')[1]}` : '';
      const resp = await api.get(`/prices/value-chart${params}`);
      const byAsset = resp.data || resp;
      flaggedSplits = resp.flagged_splits || [];
      const allDates = new Set();
      for (const code of Object.keys(byAsset || {})) {
        for (const p of byAsset[code] || []) {
          allDates.add(p.date);
        }
      }
      const labels = [...allDates].sort();
      const datasets = Object.entries(byAsset || {}).map(([code, points], i) => {
        const valueMap = new Map(points.map(p => [p.date, p.value]));
        const estimatedMap = new Map(points.map(p => [p.date, p.estimated || false]));
        return {
          label: code,
          data: labels.map(d => valueMap.get(d) ?? 0),
          estimated: labels.map(d => estimatedMap.get(d) || false),
          color: CHART_COLORS[i % CHART_COLORS.length],
        };
      });
      allPricesData = { labels, datasets };
    } catch {
      allPricesData = { labels: [], datasets: [] };
    } finally {
      pricesLoading = false;
    }
  }

  async function handleSyncPrices() {
    syncing = true;
    error = null;
    try {
      await api.post('/market/sync-prices');
      if (selectedAsset) await loadPriceHistory(selectedAsset.market_code);
      await loadAllPrices();
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
      const range = getPriceRange();
      const params = range ? `?start_date=${range.split('/')[0]}&end_date=${range.split('/')[1]}` : '';
      const points = await api.get(`/prices/chart/${encodeURIComponent(marketCode)}${params}`);
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

  async function reloadPriceCharts() {
    await loadAllPrices();
    if (selectedAsset) await loadPriceHistory(selectedAsset.market_code);
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

  onMount(async () => {
    await loadAll();
    loadAllPrices();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('portfolio-assets'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('portfolio-assets');
    if (on && !_tutWasOn) loadAll().then(() => loadAllPrices());
    _tutWasOn = on;
  });

  async function handleConfirmSplit() {
    if (!confirmSplit) return;
    confirmingSplit = true;
    try {
      await api.post('/stock-splits', {
        market_code: confirmSplit.market_code,
        split_date: confirmSplit.buy_date,
        ratio: confirmSplit.inferred_ratio,
      });
      confirmSplit = null;
      await loadAllPrices();
    } catch {
      confirmSplit = null;
    } finally {
      confirmingSplit = false;
    }
  }
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('portfolioAssets.title')}</h1>
    <ReplayButton page="portfolio-assets" />
  </div>
  <div class="page-actions">
    {#if currencyCodes.length > 0}
      <Select
        value={_displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { setDisplayCurrency(e.target.value); loadAll(); }}
      />
    {/if}
    <Button variant="secondary" size="sm" onclick={handleSyncPrices} disabled={syncing}>
      {syncing ? t('portfolioAssets.syncing') : t('portfolioAssets.syncPrices')}
    </Button>
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('portfolioAssets.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('portfolioAssets.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if portfolioAssets.length === 0}
  <EmptyState title={t('portfolioAssets.emptyTitle')} message={t('portfolioAssets.emptyMsg')} />
{:else}
  <div class="date-presets">
    {#each PRICE_PRESETS as preset}
      <button
        class="preset-btn"
        class:active={pricePreset === preset.value}
        onclick={() => { pricePreset = preset.value; reloadPriceCharts(); }}
      >{preset.label}</button>
    {/each}
    {#if pricePreset === 'custom'}
      <TextInput type="date" placeholder="Start" value={priceCustomStart} oninput={(e) => { priceCustomStart = e.target.value; reloadPriceCharts(); }} />
      <span class="custom-sep">—</span>
      <TextInput type="date" placeholder="End" value={priceCustomEnd} oninput={(e) => { priceCustomEnd = e.target.value; reloadPriceCharts(); }} />
    {/if}
    {#if pricesLoading}
      <span class="loading-indicator"></span>
    {/if}
  </div>

  {#if flaggedSplits.length > 0}
    <div class="split-banner">
      {#each flaggedSplits as fs}
        <div class="split-banner-item">
          <span class="split-banner-text">
            Potential split for <strong>{fs.market_code}</strong>: buy {fs.buy_price}, market {fs.market_price}, ratio ~{fs.inferred_ratio}:1
          </span>
          <Button variant="primary" size="sm" onclick={() => confirmSplit = fs}>Confirm</Button>
        </div>
      {/each}
    </div>
  {/if}

  {#if allPricesData.labels.length > 0}
    <div class="overview-chart">
      <ChartCard title={t('portfolioAssets.holdingsValueOverTime')}>
        <StackedAreaChart labels={allPricesData.labels} datasets={allPricesData.datasets} height={320} />
      </ChartCard>
    </div>
  {/if}

  <div class="filter-bar">
    <div class="filter-group">
      <TextInput bind:value={searchQuery} placeholder={t('portfolioAssets.search')} />
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
          <th>{t('portfolioAssets.marketCode')}</th>
          <th>{t('common.name')}</th>
          <th>{t('common.type')}</th>
          <th>{t('common.currency')}</th>
          <th>{t('portfolioAssets.layer')}</th>
          <th>{t('portfolioAssets.dca')}</th>
          <th class="num">{t('portfolioAssets.unrealizedPLPct')}</th>
          <th class="num">{t('portfolioAssets.desiredPct')}</th>
          <th class="num">{t('portfolioAssets.currentValue')}</th>
          <th>{t('portfolioAssets.status')}</th>
          <th class="actions-th">{t('common.actions')}</th>
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
            <td class="num">{asset.unrealized_pl_pct != null ? `${asset.unrealized_pl_pct.toFixed(2)}%` : '-'}</td>
            <td class="num">{asset.desired_weight != null ? `${asset.desired_weight}%` : '-'}</td>
            <td class="num">{asset.current_value != null ? `${_currencySymbol}${asset.current_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '-'}</td>
            <td>
              <span class="badge {asset.is_active ? 'badge-success' : 'badge-default'}">
                {asset.is_active ? t('portfolioAssets.active') : t('portfolioAssets.closed')}
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
      <ChartCard title={t('portfolioAssets.priceHistory', { code: selectedAsset.market_code })}>
        {#if priceLoading}
          <LoadingSpinner message={t('portfolioAssets.loadingPrices')} />
        {:else if priceData.values.length > 0}
          <LineChart
            labels={priceData.labels}
            datasets={[{ data: priceData.values, label: selectedAsset.market_code }]}
            currencySymbol={getSymbolFor(selectedAsset.displayCurrency)}
          />
        {:else}
          <EmptyState title={t('portfolioAssets.noPriceData')} message={t('portfolioAssets.noPriceDataMsg')} />
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
  title={t('portfolioAssets.deleteTitle')}
  entityName={deletingAsset ? `${deletingAsset.market_code}` : ''}
  message={t('portfolioAssets.deleteMsg')}
/>

<TutorialOverlay definition={portfolioAssetsTutorial} page="portfolio-assets" onfinish={() => { loadAll().then(() => loadAllPrices()); }} />

{#if confirmSplit}
  <div class="modal-overlay" onclick={() => confirmSplit = null} role="presentation"></div>
  <div class="modal-panel">
    <h3>Confirm Stock Split</h3>
    <div class="split-details">
      <p><strong>{confirmSplit.market_code}</strong></p>
      <p>Buy date: {confirmSplit.buy_date}</p>
      <p>Buy price: {confirmSplit.buy_price}</p>
      <p>Market price: {confirmSplit.market_price}</p>
      <p>Inferred ratio: <strong>{confirmSplit.inferred_ratio}:1</strong></p>
    </div>
    <div class="modal-actions">
      <Button variant="outline" size="sm" onclick={() => confirmSplit = null}>{t('common.cancel')}</Button>
      <Button variant="primary" size="sm" onclick={handleConfirmSplit} disabled={confirmingSplit}>
        {confirmingSplit ? t('common.saving') : 'Confirm Split'}
      </Button>
    </div>
  </div>
{/if}

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

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
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

  .overview-chart { margin-bottom: var(--space-6); }

  .date-presets {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }

  .preset-btn {
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text-secondary);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .preset-btn:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .preset-btn.active {
    background: var(--color-primary);
    color: #fff;
    border-color: var(--color-primary);
  }

  .custom-sep {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  .loading-indicator {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--color-border);
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    margin-left: var(--space-2);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

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

  .split-banner {
    background: var(--color-warning-light, rgba(240, 140, 0, 0.1));
    border: 1px solid var(--color-warning, #f08c00);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    margin-bottom: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .split-banner-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .split-banner-text {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: var(--z-modal-backdrop, 100);
  }

  .modal-panel {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    z-index: calc(var(--z-modal-backdrop, 100) + 1);
    min-width: 360px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  }

  .modal-panel h3 {
    margin: 0 0 var(--space-4) 0;
    font-size: var(--font-size-lg);
  }

  .split-details {
    margin-bottom: var(--space-4);
  }

  .split-details p {
    margin: var(--space-1) 0;
    font-size: var(--font-size-sm);
  }

  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    margin-top: var(--space-4);
  }
</style>
