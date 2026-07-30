<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import DoughnutChart from '$lib/components/charts/DoughnutChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import AddTransactionModal from '$lib/components/modals/AddTransactionModal.svelte';
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
  let addModalOpen = $state(false);

  let currentPage = $state(1);
  const ITEMS_PER_PAGE = 10;

  let paginatedTxns = $derived(
    dividendTxns.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
  );

  let totalDividends = $derived(
    dividends.reduce((sum, d) => sum + (d.total_dividends || 0), 0)
  );

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0'];

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [divData, txns, paList, maList] = await Promise.all([
        analytics.dividends(),
        crud.transactions.getList(),
        crud.portfolioAssets.getList(),
        crud.marketAssets.getList(),
      ]);
      dividends = divData || [];

      dividendTxns = txns
        .filter(t => t.type === 'DIVIDEND')
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

  onMount(async () => {
    const wasResumed = await tutorialStore.resume('dividends', dividendsTutorial, dividendsMock);
    if (!wasResumed) {
      if (tutorialStore.isActive()) {
        await tutorialStore.skip();
      }
      const shouldStart = !tutorialStore.isPageSeen('dividends');
      if (shouldStart) {
        await tutorialStore.start('dividends', dividendsTutorial);
      }
    }

    loadAll();
  });
</script>

<div class="page-header">
  <h1 class="page-title">{t('dividends.title')}</h1>
  <div style="display: flex; gap: var(--space-2);">
    <ReplayButton onclick={() => tutorialStore.start('dividends', dividendsTutorial)} />
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
    <MetricCard label={t('dividends.totalDividends')} value={totalDividends} />
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
            data={dividends.map(d => d.total_dividends)}
            colors={chartColors}
          />
        </ChartCard>
        <div class="summary-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>{t('transactions.asset')}</th>
                <th>{t('common.currency')}</th>
                <th class="num">{t('income.total')}</th>
                <th class="num">{t('dividends.payments')}</th>
              </tr>
            </thead>
            <tbody>
              {#each dividends as d (d.market_code || d.portfolio_asset_id)}
                <tr>
                  <td class="cell-name">{d.ticker || d.market_code || '-'}</td>
                  <td>{d.currency}</td>
                  <td class="num">{d.total_dividends?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
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
              <th>{t('common.notes')}</th>
            </tr>
          </thead>
          <tbody>
            {#each paginatedTxns as tx (tx.id)}
              <tr>
                <td>{new Date(tx.timestamp).toLocaleDateString()}</td>
                <td class="cell-name">{getAssetName(tx.portfolio_asset_id)}</td>
                <td class="num">{tx.total_value?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td>{tx.currency}</td>
                <td class="cell-notes">{tx.notes || '-'}</td>
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

<AddTransactionModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} defaultType="DIVIDEND" />

<TutorialOverlay definition={dividendsTutorial} page="dividends" onfinish={loadAll} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
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

  .data-table th {
    padding: var(--space-3) var(--space-4);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  .data-table th.num {
    text-align: right;
  }

  .data-table td {
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

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-muted);
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
