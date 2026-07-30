<script>
  import { onMount } from 'svelte';
  import { analytics } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import Button from '$lib/components/Button.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { performance as performanceTutorial } from '$lib/tutorial/definitions/index';
  import performanceMock from '$lib/tutorial/mocks/performance';

  tutorialStore.registerMock('performance', performanceMock);

  let loading = $state(true);
  let error = $state(null);
  let performance = $state(null);
  let realizedGains = $state([]);

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0'];

  function formatPct(val) {
    if (val == null) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  }

  function formatCurrency(val) {
    if (val == null) return '-';
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [perf, gains] = await Promise.all([
        analytics.performance(),
        analytics.realizedGains(),
      ]);
      performance = perf;
      realizedGains = gains || [];
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'performance data' });
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    const wasResumed = await tutorialStore.resume('performance', performanceTutorial, performanceMock);
    if (!wasResumed) {
      if (tutorialStore.isActive()) {
        await tutorialStore.skip();
      }
      const shouldStart = !tutorialStore.isPageSeen('performance');
      if (shouldStart) {
        await tutorialStore.start('performance', performanceTutorial);
      }
    }

    loadAll();
  });
</script>

<div class="page-header">
  <h1 class="page-title">{t('performance.title')}</h1>
  <div class="page-actions">
    <ReplayButton page="performance" />
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('performance.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if !performance}
  <EmptyState title={t('performance.emptyTitle')} message={t('performance.emptyMsg')} />
{:else}
  <div class="metric-grid">
    <MetricCard label={t('dashboard.portfolioValue')} value={performance.total_portfolio_value} />
    <MetricCard label={t('performance.totalInvested')} value={performance.total_invested} />
    <MetricCard
      label={t('performance.totalReturn')}
      value={formatPct(performance.total_return_pct)}
      variant={performance.total_return_pct >= 0 ? 'positive' : 'negative'}
    />
    <MetricCard
      label={t('performance.unrealizedPL')}
      value={performance.total_unrealized_pl}
      variant={performance.total_unrealized_pl >= 0 ? 'positive' : 'negative'}
    />
    <MetricCard
      label={t('performance.realizedPL')}
      value={performance.total_realized_pl}
      variant={performance.total_realized_pl >= 0 ? 'positive' : 'negative'}
    />
  </div>

  {#if realizedGains.length > 0}
    <div class="section">
      <h2 class="section-title">{t('performance.realizedGains')}</h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>{t('transactions.asset')}</th>
              <th>{t('performance.sellDate')}</th>
              <th class="num">{t('performance.qty')}</th>
              <th class="num">{t('performance.sellPrice')}</th>
              <th class="num">{t('performance.sellTotal')}</th>
              <th class="num">{t('performance.costBasis')}</th>
              <th class="num">{t('performance.pl')}</th>
              <th class="num">{t('performance.plPct')}</th>
              <th>{t('common.currency')}</th>
            </tr>
          </thead>
          <tbody>
            {#each realizedGains as gain (gain.transaction_id)}
              <tr>
                <td class="cell-name">{gain.ticker || gain.market_code || '-'}</td>
                <td>{gain.sell_date}</td>
                <td class="num">{gain.sell_quantity?.toLocaleString()}</td>
                <td class="num">{gain.sell_price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td class="num">{gain.sell_total?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td class="num">{gain.cost_basis?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td class="num {gain.realized_pl >= 0 ? 'positive' : 'negative'}">
                  {gain.realized_pl >= 0 ? '+' : ''}{gain.realized_pl?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </td>
                <td class="num {gain.realized_pl_pct >= 0 ? 'positive' : 'negative'}">
                  {formatPct(gain.realized_pl_pct)}
                </td>
                <td>{gain.currency}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {:else}
    <div class="section">
      <h2 class="section-title">{t('performance.realizedGains')}</h2>
      <p class="no-data">{t('performance.noRealizedGains')}</p>
    </div>
  {/if}
{/if}

<TutorialOverlay definition={performanceTutorial} page="performance" onfinish={loadAll} />

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

  .positive {
    color: var(--color-success);
  }

  .negative {
    color: var(--color-danger);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .no-data {
    text-align: center;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    padding: var(--space-6);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
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
