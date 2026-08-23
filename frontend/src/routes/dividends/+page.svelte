<script>
  import { onMount } from 'svelte';
  import { analytics, crud, currenciesApi } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte.ts';
  import { LoadingSpinner, EmptyState, Pagination, SortableTh } from '$lib/components/index.js';
  import { createTableSort } from '$lib/utils/tableSort.svelte.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import Select from '$lib/components/Select.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import DoughnutChart from '$lib/components/charts/DoughnutChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import AddTransactionModal from '$lib/components/modals/AddTransactionModal.svelte';
  import EditTransactionModal from '$lib/components/modals/EditTransactionModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { dividends as dividendsTutorial } from '$lib/tutorial/definitions/index';
  import dividendsMock from '$lib/tutorial/mocks/dividends';

  tutorialStore.registerMock('dividends', dividendsMock);

  let loading = $state(true);
  let error = $state(null);
  let dividends = $state([]);
  let dividendTxns = $state([]);
  let portfolioAssets = $state({});
  let marketAssets = $state({});
  let currencyCodes = $state([]);
  let addModalOpen = $state(false);
  let editModalOpen = $state(false);
  let editingTransaction = $state(null);
  let deleteModalOpen = $state(false);
  let deletingTransaction = $state(null);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 10;

  let paginatedTxns = $derived(
    dividendTxns.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
  );

  let totalDividends = $derived(
    dividends.reduce((sum, d) => sum + (d.total_dividends_display ?? d.total_dividends ?? 0), 0)
  );

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0'];

  const ASSET_COLUMNS = [
    { key: 'asset', labelKey: 'transactions.asset', align: 'left', accessor: (d) => d.ticker || d.market_code || '' },
    { key: 'total_dividends', labelKey: 'dividends.originalAmount', align: 'right', numeric: true },
    { key: 'total_dividends_display', labelKey: 'dividends.amount', align: 'right', numeric: true, accessor: (d) => d.total_dividends_display ?? d.total_dividends ?? 0 },
    { key: 'count', labelKey: 'dividends.payments', align: 'right', numeric: true },
  ];

  const assetSorter = createTableSort(ASSET_COLUMNS, { initialKey: 'total_dividends_display', initialDir: 'desc' });

  let sortedDividends = $derived(assetSorter.sorted(dividends));

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [divData, txns, paList, maList] = await Promise.all([
        analytics.dividends({ displayCurrency: _displayCurrency }),
        crud.transactions.getList(),
        crud.portfolioAssets.getList(),
        crud.marketAssets.getList(),
      ]);
      dividends = divData || [];

      dividendTxns = txns
        .filter(t => t.income_category === 'dividends')
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      const paMap = {};
      for (const pa of paList) paMap[pa.id] = pa;
      portfolioAssets = paMap;

      const maMap = {};
      for (const ma of maList) maMap[ma.market_code] = ma;
      marketAssets = maMap;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'dividend data' });
    } finally {
      loading = false;
    }
  }

  function getAssetName(portfolioAssetId) {
    const pa = portfolioAssets[portfolioAssetId];
    if (!pa) return '-';
    const ma = marketAssets[pa.market_code];
    return ma?.name || ma?.ticker || pa.market_code;
  }

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
      error = e.message || t('common.errorPrefix', { resource: 'dividend data' });
      deleteModalOpen = false;
      deletingTransaction = null;
    }
  }

  onMount(async () => {
    try {
      currencyCodes = await currenciesApi.getList();
    } catch (_) {}
    await loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('dividends'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('dividends');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('dividends.title')}</h1>
    <ReplayButton page="dividends" />
  </div>
  <div style="display: flex; gap: var(--space-2);">
    {#if currencyCodes.length > 0}
      <Select
        value={_displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { setDisplayCurrency(e.target.value); loadAll(); }}
      />
    {/if}
    <Button variant="primary" onclick={() => addModalOpen = true}>{t('dividends.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('dividends.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if dividends.length === 0 && dividendTxns.length === 0}
  <EmptyState title={t('dividends.emptyTitle')} message={t('dividends.emptyMsg')} />
{:else}
  <div class="metric-grid">
    <MetricCard label={t('dividends.totalDividends')} value={totalDividends} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} />
    <MetricCard label={t('dividends.assetsWithDividends')} value={String(dividends.length)} />
    <MetricCard label={t('dividends.totalPayments')} value={String(dividendTxns.length)} />
  </div>

  {#if dividends.length > 0}
    <div class="section">
      <h2 class="section-title">{t('dividends.byAsset')}</h2>
      <div class="charts-grid">
        <ChartCard title={t('dividends.distribution')}>
          <DoughnutChart
            labels={dividends.map(d => d.ticker || d.market_code || t('dividends.unknown'))}
            data={dividends.map(d => d.total_dividends_display ?? d.total_dividends)}
            colors={chartColors}
            currencySymbol={_currencySymbol}
          />
        </ChartCard>
        <div class="summary-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                {#each ASSET_COLUMNS as col}
                  <SortableTh {col} sorter={assetSorter} />
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each sortedDividends as d (d.market_code || d.portfolio_asset_id)}
                <tr>
                  <td class="cell-name">{d.ticker || d.market_code || '-'}</td>
                  <td class="num">{getSymbolFor(d.currency)}{(d.total_dividends ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                  <td class="num">{_currencySymbol}{(d.total_dividends_display ?? d.total_dividends ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                  <td class="num">{d.count}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {/if}

  {#if dividendTxns.length > 0}
    <div class="table-section">
      <h2 class="section-title">{t('dividends.transactions')}</h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>{t('common.date')}</th>
              <th>{t('transactions.asset')}</th>
              <th class="num">{t('common.amount')}</th>
              <th>{t('common.currency')}</th>
              <th>{t('modals.dividendType')}</th>
              <th>{t('common.notes')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each paginatedTxns as tx (tx.id)}
              <tr>
                <td>{new Date(tx.timestamp).toLocaleDateString()}</td>
                <td class="cell-name">{getAssetName(tx.portfolio_asset_id)}</td>
                <td class="num">{tx.total_value?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td>{tx.currency}</td>
                <td>{tx.dividend_type || '-'}</td>
                <td class="cell-notes">{tx.notes || '-'}</td>
                <td class="actions-cell">
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
        totalItems={dividendTxns.length}
        itemsPerPage={ITEMS_PER_PAGE}
        bind:currentPage={currentPage}
      />
    </div>
  {/if}
{/if}

<AddTransactionModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} defaultType="INCOME" defaultCategory="dividends" />
<EditTransactionModal open={editModalOpen} transaction={editingTransaction} onclose={() => { editModalOpen = false; editingTransaction = null; }} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteModalOpen}
  onclose={() => { deleteModalOpen = false; deletingTransaction = null; }}
  onconfirm={confirmDelete}
  title={t('transactions.deleteTitle')}
  entityName={deletingTransaction ? `${deletingTransaction.total_value} - ${deletingTransaction.currency}` : ''}
  message={t('transactions.deleteMsg')}
/>

<TutorialOverlay definition={dividendsTutorial} page="dividends" onfinish={loadAll} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .section {
    margin-bottom: var(--space-6);
  }

  .section-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    margin: 0 0 var(--space-3) 0;
  }

  .charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-5);
  }

  .summary-table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    align-self: start;
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

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .data-table :global(th) {
    padding: var(--space-3) var(--space-4);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  .data-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .num,
  .data-table :global(th.num) {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-muted);
  }

  .actions-cell {
    text-align: right;
    white-space: nowrap;
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    color: var(--color-text-secondary);
    border-radius: var(--radius-sm);
    transition: background 0.2s ease, color 0.2s ease;
  }

  .icon-btn:hover {
    background: var(--color-surface-alt);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
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
    .charts-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
