<script>
  import { onMount } from 'svelte';
  import { analytics, currenciesApi } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { t, locale } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import { LoadingSpinner, EmptyState, MetricGroup } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
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
  let currencyCodes = $state([]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0'];

  function formatPct(val) {
    if (val == null) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  }

  function formatPctValue(val) {
    if (val == null) return '-';
    return `${val.toFixed(2)}%`;
  }

  function formatCurrency(val) {
    if (val == null) return '-';
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  let sortKey = $state('sell_date');
  let sortDir = $state('desc');

  const NUMERIC_SORT_KEYS = new Set([
    'sell_quantity',
    'sell_price',
    'sell_total',
    'cost_basis',
    'realized_pl',
    'realized_pl_pct',
  ]);

  const GAIN_COLUMNS = [
    { key: 'ticker', labelKey: 'transactions.asset', align: 'left', accessor: (g) => g.ticker || g.market_code || '' },
    { key: 'sell_date', labelKey: 'performance.sellDate', align: 'left' },
    { key: 'sell_quantity', labelKey: 'performance.qty', align: 'right' },
    { key: 'sell_price', labelKey: 'performance.sellPrice', align: 'right' },
    { key: 'sell_total', labelKey: 'performance.sellTotal', align: 'right' },
    { key: 'cost_basis', labelKey: 'performance.costBasis', align: 'right' },
    { key: 'realized_pl', labelKey: 'performance.pl', align: 'right' },
    { key: 'realized_pl_pct', labelKey: 'performance.plPct', align: 'right' },
    { key: 'currency', labelKey: 'common.currency', align: 'left' },
  ];

  function handleSort(key) {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortDir = NUMERIC_SORT_KEYS.has(key) ? 'desc' : 'asc';
    }
  }

  function gainValue(gain, col) {
    return col.accessor ? col.accessor(gain) : gain[col.key];
  }

  let sortedGains = $derived.by(() => {
    const col = GAIN_COLUMNS.find((c) => c.key === sortKey) || GAIN_COLUMNS[1];
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...realizedGains].sort((a, b) => {
      let av = gainValue(a, col);
      let bv = gainValue(b, col);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir;
    });
  });

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [perf, gains] = await Promise.all([
        analytics.performance(_displayCurrency, locale()),
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
    try {
      currencyCodes = await currenciesApi.getList();
    } catch (_) {}
    await loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('performance'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('performance');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });

  let affectedCurrencies = $derived.by(() => {
    const fallbacks = performance?.rate_fallbacks || [];
    const byCode = new Map();
    for (const f of fallbacks) {
      if (!f?.currency) continue;
      const existing = byCode.get(f.currency);
      const date = f.requested_date ? new Date(f.requested_date) : null;
      if (!existing) {
        byCode.set(f.currency, { code: f.currency, firstMissing: date });
      } else if (date && (!existing.firstMissing || date < existing.firstMissing)) {
        existing.firstMissing = date;
      }
    }
    return [...byCode.values()].sort((a, b) => a.code.localeCompare(b.code));
  });

  let syncingRates = $state(false);
  let rateSyncNote = $state(null);

  async function handleRateSync() {
    syncingRates = true;
    rateSyncNote = null;
    try {
      const resp = await api.post('/currencies/sync');
      if (resp?.circuit_open) {
        rateSyncNote = t('currencies.syncUnavailable');
      } else {
        await loadAll();
      }
    } catch (e) {
      rateSyncNote = e.message || 'Sync failed';
    } finally {
      syncingRates = false;
    }
  }
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('performance.title')}</h1>
    <ReplayButton page="performance" />
  </div>
  {#if !loading && !error && performance?.rate_fallbacks?.length > 0}
    <div class="rate-warning-inline" role="status">
      <span class="rw-icon">⚠</span>
      <span class="rw-text">
        <strong>{t('performance.rateFallbackTitle')}</strong>
        {t('performance.rateFallbackMsg')}{#if affectedCurrencies.length}:{/if}
        {#each affectedCurrencies as c, i}{i > 0 ? ', ' : ''}<span class="rw-code">{c.code}</span>{#if c.firstMissing} ({c.firstMissing.toLocaleDateString()}){/if}{/each}
      </span>
      <button class="rw-sync" onclick={handleRateSync} disabled={syncingRates}>
        {syncingRates ? t('currencies.syncing') : t('currencies.syncRates')}
      </button>
      {#if rateSyncNote}
        <span class="rw-note">{rateSyncNote}</span>
      {/if}
    </div>
  {/if}
  <div class="page-actions">
    {#if currencyCodes.length > 0}
      <Select
        value={_displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { setDisplayCurrency(e.target.value); loadAll(); }}
      />
    {/if}
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
  <div class="groups">
    <MetricGroup class="band-portfolio" label={t('performance.groupPortfolio')} tone="market">
      <MetricCard compact label={t('dashboard.portfolioValue')} value={performance.total_portfolio_value} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('performance.hintPortfolioValue')} />
      <MetricCard compact label={t('performance.totalInvestedNow')} value={performance.total_invested_now} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('performance.hintTotalInvestedNow')} />
      <MetricCard compact label={t('performance.totalInvestedHistoric')} value={performance.total_invested_historic} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('performance.hintTotalInvestedHistoric')} />
      <MetricGroup label={t('performance.groupUnrealized')} tone="unrealized">
        <MetricCard
          compact
          label={t('performance.unrealizedPLPct')}
          value={formatPctValue(performance.unrealized_pl_pct)}
          tooltip={t('performance.hintUnrealizedPLPct')}
          valueVariant={performance.unrealized_pl_pct >= 0 ? 'positive' : 'negative'}
        />
        <MetricCard
          compact
          label={t('performance.unrealizedPL')}
          value={performance.total_unrealized_pl}
          tooltip={t('performance.hintUnrealizedPL')}
          currencySymbol={_currencySymbol}
          currencyCode={_displayCurrency}
          valueVariant={performance.total_unrealized_pl >= 0 ? 'positive' : 'negative'}
        />
      </MetricGroup>
    </MetricGroup>
    <MetricGroup class="band-realized" label={t('performance.groupRealized')} tone="realized">
      <MetricCard
        compact
        label={t('performance.totalReturn')}
        value={formatPctValue(performance.total_return_pct)}
        tooltip={t('performance.hintTotalReturn')}
        valueVariant={performance.total_return_pct >= 0 ? 'positive' : 'negative'}
      />
      <MetricCard
        compact
        label={t('performance.totalReturnValue')}
        value={performance.total_return}
        tooltip={t('performance.hintTotalReturn')}
        currencySymbol={_currencySymbol}
        currencyCode={_displayCurrency}
        valueVariant={performance.total_return >= 0 ? 'positive' : 'negative'}
      />
      <MetricGroup label={t('performance.groupTrading')} tone="total">
        <MetricCard
          compact
          label={t('performance.realizedPLPct')}
          value={formatPctValue(performance.realized_pl_pct)}
          tooltip={t('performance.hintRealizedPLPct')}
          valueVariant={performance.realized_pl_pct >= 0 ? 'positive' : 'negative'}
        />
        <MetricCard
          compact
          label={t('performance.realizedPL')}
          value={performance.total_realized_pl}
          tooltip={t('performance.hintRealizedPL')}
          currencySymbol={_currencySymbol}
          currencyCode={_displayCurrency}
          valueVariant={performance.total_realized_pl >= 0 ? 'positive' : 'negative'}
        />
      </MetricGroup>
      <MetricGroup label={t('performance.groupIncome')} tone="income">
        <MetricCard
          compact
          label={t('performance.dividends')}
          value={performance.total_dividends}
          change={performance.dividend_yield_pct?.toFixed(2)}
          changeLabel={t('performance.yieldOfInvested')}
          variant={performance.dividend_yield_pct >= 0 ? 'positive' : 'negative'}
          tooltip={t('performance.hintDividends')}
          currencySymbol={_currencySymbol}
          currencyCode={_displayCurrency}
        />
        <MetricCard
          compact
          label={t('performance.interest')}
          value={performance.total_interest}
          tooltip={t('performance.hintInterest')}
          currencySymbol={_currencySymbol}
          currencyCode={_displayCurrency}
        />
      </MetricGroup>
    </MetricGroup>
  </div>

      {#if realizedGains.length > 0}
        <div class="section">
          <h2 class="section-title">{t('performance.realizedGains')}</h2>
          <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                {#each GAIN_COLUMNS as col}
                  <th
                    class="sortable-th"
                    class:num={col.align === 'right'}
                    class:sort-active={sortKey === col.key}
                    onclick={() => handleSort(col.key)}
                  >
                    {t(col.labelKey)}
                    <span class="sort-indicator">{sortKey === col.key ? (sortDir === 'asc' ? '▲' : '▼') : ''}</span>
                  </th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each sortedGains as gain (gain.transaction_id)}
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
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .rate-warning-inline {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    min-width: 0;
    max-width: 640px;
    margin-left: auto;
    padding: 2px 10px;
    background: var(--color-warning-bg, #fff3cd);
    border: 1px solid var(--color-warning-border, #ffc107);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    line-height: 1.4;
    color: var(--color-text-primary);
  }

  .rw-icon {
    color: var(--color-warning, #856404);
    flex-shrink: 0;
  }

  .rw-text strong {
    color: var(--color-warning, #856404);
    font-weight: var(--font-weight-semibold);
  }

  .rw-code {
    color: var(--color-warning, #856404);
    font-weight: var(--font-weight-semibold);
  }

  .rw-sync {
    flex-shrink: 0;
    padding: 2px 10px;
    background: transparent;
    border: 1px solid var(--color-warning-border, #ffc107);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--color-warning, #856404);
    cursor: pointer;
  }

  .rw-sync:hover:not(:disabled) {
    background: var(--color-warning-bg, #fff3cd);
  }

  .rw-sync:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .rw-note {
    flex-basis: 100%;
    color: var(--color-warning, #856404);
  }

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-shrink: 0;
  }

  @media (max-width: 768px) {
    .rate-warning-inline {
      display: none;
    }
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .groups {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  /* One visual row per band: free cards + nested groups share the same line.
     Anchored on the page-owned .groups wrapper because the bands themselves
     render inside the MetricGroup component. */
  .groups :global(.band-portfolio > .group-body) {
    grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 2fr);
  }

  .groups :global(.band-realized > .group-body) {
    grid-template-columns: repeat(2, minmax(0, 1fr)) repeat(2, minmax(0, 2fr));
  }

  .groups :global(.band-portfolio .metric-group),
  .groups :global(.band-realized .metric-group) {
    margin-top: var(--space-3);
    height: calc(100% - var(--space-3));
  }

  @media (max-width: 1100px) {
    .groups :global(.band-portfolio > .group-body),
    .groups :global(.band-realized > .group-body) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .groups :global(.band-portfolio .metric-group),
    .groups :global(.band-realized .metric-group) {
      height: auto;
      margin-top: var(--space-2);
    }
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
