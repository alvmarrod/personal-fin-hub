<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { analytics, currenciesApi } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import StackedBarChart from '$lib/components/charts/StackedBarChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { cashFlow as cashFlowTutorial } from '$lib/tutorial/definitions/index';
  import cashFlowMock from '$lib/tutorial/mocks/cash-flow';

  tutorialStore.registerMock('cash-flow', cashFlowMock);
  if (!tutorialStore.isPageSeen('cash-flow')) {
    tutorialStore.start('cash-flow', cashFlowTutorial);
  }

  let loading = $state(true);
  let error = $state(null);
  let cashFlow = $state(null);
  let currencyCodes = $state([]);
  let rateInfo = $state(null);

  let activePreset = $state('6m');
  let customStart = $state('');
  let customEnd = $state('');

  let PRESETS = $derived([
    { key: '3m', label: t('common.preset3m') },
    { key: '6m', label: t('common.preset6m') },
    { key: '1y', label: t('common.preset1y') },
    { key: 'all', label: t('common.presetAll') },
    { key: 'custom', label: t('common.custom') },
  ]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  function today() { return new Date(); }
  function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
  }
  function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function getRange(preset) {
    const now = today();
    switch (preset) {
      case '3m': return { start: formatDate(addMonths(now, -3)), end: formatDate(now) };
      case '6m': return { start: formatDate(addMonths(now, -6)), end: formatDate(now) };
      case '1y': return { start: formatDate(addMonths(now, -12)), end: formatDate(now) };
      case 'all': return { start: null, end: null };
      case 'custom': return { start: customStart || null, end: customEnd || null };
      default: return { start: formatDate(addMonths(now, -6)), end: formatDate(now) };
    }
  }

  function selectPreset(key) {
    activePreset = key;
    loadCashFlow();
  }

  async function loadCashFlow() {
    loading = true;
    error = null;
    try {
      const range = getRange(activePreset);
      cashFlow = await analytics.cashFlow({
        groupBy: 'month',
        startDate: range.start,
        endDate: range.end,
        displayCurrency: _displayCurrency,
      });
      rateInfo = cashFlow?.rate_info || null;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'cash flow' });
    } finally {
      loading = false;
    }
  }

  function getChartData() {
    if (!cashFlow?.lines) return { labels: [], datasets: [] };

    const periods = [...new Set(cashFlow.lines.map(l => l.period))].sort();
    const inflowMap = {};
    const outflowMap = {};
    for (const line of cashFlow.lines) {
      if (['MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL'].includes(line.type)) {
        inflowMap[line.period] = (inflowMap[line.period] || 0) + line.total_value;
      } else if (['MONEY_OUT', 'INVESTMENT_BUY'].includes(line.type)) {
        outflowMap[line.period] = (outflowMap[line.period] || 0) + line.total_value;
      }
    }

    return {
      labels: periods,
      datasets: [
        { label: t('cashFlow.inflows'), data: periods.map(p => inflowMap[p] || 0), color: '#2f9e44' },
        { label: t('cashFlow.outflows'), data: periods.map(p => -(outflowMap[p] || 0)), color: '#e03131' },
      ],
    };
  }

  onMount(async () => {
    try {
      currencyCodes = await currenciesApi.getList();
    } catch (_) {}
    loadCashFlow();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('cash-flow'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('cash-flow');
    if (on && !_tutWasOn) loadCashFlow();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('cashFlow.title')}</h1>
    <ReplayButton page="cash-flow" />
  </div>
  <div class="page-actions">
    {#if currencyCodes.length > 0}
      <Select
        value={_displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { setDisplayCurrency(e.target.value); loadCashFlow(); }}
      />
    {/if}
  </div>
</div>

{#if rateInfo}
  <div class="rate-warning">
    <span class="rate-warning-icon">⚠</span>
    <div>
      <strong>{t('cashFlow.exchangeRateNote', { date: new Date(rateInfo.latest_timestamp).toLocaleDateString() })}</strong>
      <p>{t('cashFlow.exchangeRateDetail')}</p>
    </div>
  </div>
{/if}

<div class="preset-bar">
  {#each PRESETS as p (p.key)}
    <button
      class="preset-btn"
      class:active={activePreset === p.key}
      onclick={() => selectPreset(p.key)}
    >{p.label}</button>
  {/each}
  {#if activePreset === 'custom'}
    <div class="custom-dates">
      <label>
        {t('common.from')}
        <input type="date" bind:value={customStart} onchange={() => loadCashFlow()} />
      </label>
      <label>
        {t('common.to')}
        <input type="date" bind:value={customEnd} onchange={() => loadCashFlow()} />
      </label>
    </div>
  {/if}
</div>

{#if loading}
  <LoadingSpinner message={t('cashFlow.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadCashFlow}>{t('common.retry')}</Button>
  </div>
{:else if !cashFlow || (cashFlow.total_in === 0 && cashFlow.total_out === 0)}
  <EmptyState title={t('cashFlow.emptyTitle')} message={t('cashFlow.emptyMsg')} />
{:else}
  <div class="metric-grid">
    <MetricCard label={t('cashFlow.totalInflows')} value={cashFlow.total_in} currencyCode={_displayCurrency} currencySymbol={_currencySymbol} />
    <MetricCard label={t('cashFlow.totalOutflows')} value={cashFlow.total_out} currencyCode={_displayCurrency} currencySymbol={_currencySymbol} />
    <MetricCard
      label={t('cashFlow.netCashFlow')}
      value={cashFlow.net}
      currencyCode={_displayCurrency}
      currencySymbol={_currencySymbol}
      variant={cashFlow.net >= 0 ? 'positive' : 'negative'}
    />
  </div>

  <div class="chart-section">
    <ChartCard title={t('cashFlow.byPeriod')}>
      <StackedBarChart
        labels={getChartData().labels}
        datasets={getChartData().datasets}
        currencySymbol={_currencySymbol}
      />
    </ChartCard>
  </div>

  {#if cashFlow.lines?.length > 0}
    <div class="table-section">
      <h2 class="section-title">{t('cashFlow.detail')}</h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>{t('cashFlow.period')}</th>
              <th>{t('common.type')}</th>
              <th>{t('common.currency')}</th>
              <th class="num">{t('common.amount')}</th>
              <th class="num">{t('cashFlow.count')}</th>
              <th class="actions-col">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {#each cashFlow.lines as line (line.period + line.type + line.currency)}
              <tr>
                <td>{line.period}</td>
                <td>{line.type}</td>
                <td>{line.currency}</td>
                <td class="num">{line.total_value?.toLocaleString()}</td>
                <td class="num">{line.count}</td>
                <td class="actions-cell">
                  <button class="icon-btn" title="View transactions" aria-label="View transactions for this line" onclick={() => goto(`/transactions?type=${line.type}&currency=${line.currency}&period=${line.period}`)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
{/if}

<TutorialOverlay definition={cashFlowTutorial} page="cash-flow" onfinish={loadCashFlow} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-2);
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

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .rate-warning {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    background: rgba(240, 140, 0, 0.08);
    border: 1px solid rgba(240, 140, 0, 0.2);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    margin-bottom: var(--space-6);
    font-size: var(--font-size-sm);
  }

  .rate-warning-icon {
    flex-shrink: 0;
    color: var(--color-warning);
  }

  .rate-warning strong {
    color: var(--color-warning);
  }

  .rate-warning p {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
  }

  .preset-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
  }

  .preset-btn {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
    cursor: pointer;
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
  }

  .preset-btn:hover {
    background: var(--color-surface-hover);
    border-color: var(--color-primary);
  }

  .preset-btn.active {
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

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .chart-section {
    margin-bottom: var(--space-6);
  }

  .section-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    margin: 0 0 var(--space-3) 0;
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

  .actions-col {
    width: 60px;
    text-align: center;
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
    color: var(--color-primary);
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
