<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { analytics, currenciesApi } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { formatDate as formatDateLocale, formatMonthYear } from '$lib/utils/format.svelte';
  import { formatAmount, formatRate } from '$lib/utils/format.svelte.ts';
  import { LoadingSpinner, EmptyState, InfoTip } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import StackedBarChart from '$lib/components/charts/StackedBarChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { cashFlow as cashFlowTutorial } from '$lib/tutorial/definitions/index';
  import cashFlowMock from '$lib/tutorial/mocks/cash-flow';

  tutorialStore.registerMock('cash-flow', cashFlowMock);

  let loading = $state(true);
  let error = $state(null);
  let cashFlow = $state(null);
  let currencyCodes = $state([]);
  let rateInfo = $state(null);

  let activePreset = $state('6m');
  let customStart = $state('');
  let customEnd = $state('');

  let expandedGroups = $state(new Set());
  let expandedPeriods = $state(new Set());
  let expandedTypes = $state(new Set());
  let txCache = $state({});
  let txLoading = $state(new Set());

  const INFLOW_TYPES = ['INCOME', 'INVESTMENT_SELL'];
  const OUTFLOW_TYPES = ['MONEY_OUT', 'INVESTMENT_BUY'];

  const TYPE_LABELS = {
    INCOME: 'cashFlow.income',
    INVESTMENT_SELL: 'cashFlow.investmentSell',
    MONEY_OUT: 'cashFlow.moneyOut',
    INVESTMENT_BUY: 'cashFlow.investmentBuy',
  };

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
    expandedGroups = new Set();
    expandedPeriods = new Set();
    expandedTypes = new Set();
    txCache = {};
    txLoading = new Set();
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

  let inflowLines = $derived(cashFlow?.lines ? groupLines(cashFlow.lines, INFLOW_TYPES) : []);
  let outflowLines = $derived(cashFlow?.lines ? groupLines(cashFlow.lines, OUTFLOW_TYPES) : []);
  let inflowTotal = $derived(cashFlow?.lines ? groupTotal(cashFlow.lines, INFLOW_TYPES) : 0);
  let outflowTotal = $derived(cashFlow?.lines ? groupTotal(cashFlow.lines, OUTFLOW_TYPES) : 0);

  function groupLines(lines, types) {
    return lines.filter(l => types.includes(l.type));
  }

  function typeKey(line) {
    return `${line.period}|${line.type}|${line.currency}|${line.category || ''}`;
  }

  function toggleGroup(group) {
    const next = new Set(expandedGroups);
    if (next.has(group)) next.delete(group);
    else next.add(group);
    expandedGroups = next;
  }

  function toggleType(key) {
    const next = new Set(expandedTypes);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    expandedTypes = next;
  }

  async function loadTransactions(key, line) {
    if (txCache[key]) return;
    txLoading = new Set([...txLoading, key]);
    try {
      const range = getRange(activePreset);
      const result = await analytics.cashFlowTransactions({
        groupBy: 'month',
        period: line.period,
        type: line.type,
        category: line.category,
        currency: line.currency,
        startDate: range.start,
        endDate: range.end,
        displayCurrency: _displayCurrency,
      });
      txCache = { ...txCache, [key]: result };
    } catch (_) {
      txCache = { ...txCache, [key]: { transactions: [], total_count: 0 } };
    } finally {
      txLoading = new Set([...txLoading].filter(k => k !== key));
    }
  }

  function typeTotal(lines, type) {
    return lines.filter(l => l.type === type).reduce((s, l) => s + l.total_value, 0);
  }

  function groupTotal(lines, types) {
    return lines.filter(l => types.includes(l.type)).reduce((s, l) => s + l.total_value, 0);
  }

  function periodKey(group, period) {
    return `${group}|${period}`;
  }

  function periodsForGroup(lines) {
    return [...new Set(lines.map(l => l.period))].sort().reverse();
  }

  function periodTotal(lines, period) {
    return lines.filter(l => l.period === period).reduce((s, l) => s + l.total_value, 0);
  }

  function formatPeriod(period) {
    const [year, month] = period.split('-');
    const d = new Date(Number(year), Number(month) - 1);
    return formatMonthYear(d);
  }

  function togglePeriod(key) {
    const next = new Set(expandedPeriods);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    expandedPeriods = next;
  }

  function getChartData() {
    if (!cashFlow?.lines) return { labels: [], datasets: [] };

    const periods = [...new Set(cashFlow.lines.map(l => l.period))].sort();
    const byType = {};
    for (const t of ['INCOME', 'INVESTMENT_SELL', 'MONEY_OUT', 'INVESTMENT_BUY']) {
      byType[t] = {};
      for (const l of cashFlow.lines) {
        if (l.type === t) {
          byType[t][l.period] = (byType[t][l.period] || 0) + l.total_value;
        }
      }
    }

    return {
      labels: periods,
      datasets: [
        { label: t('cashFlow.income'), data: periods.map(p => byType.INCOME[p] || 0), color: '#2f9e44', stack: 'inflows' },
        { label: t('cashFlow.investmentSell'), data: periods.map(p => byType.INVESTMENT_SELL[p] || 0), color: '#69db7c', stack: 'inflows' },
        { label: t('cashFlow.moneyOut'), data: periods.map(p => -(byType.MONEY_OUT[p] || 0)), color: '#e03131', stack: 'outflows' },
        { label: t('cashFlow.investmentBuy'), data: periods.map(p => -(byType.INVESTMENT_BUY[p] || 0)), color: '#ffa8a8', stack: 'outflows' },
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

{#if rateInfo?.stale}
  <div class="rate-warning">
    <span class="rate-warning-icon">⚠</span>
    <div>
      <strong>{t('cashFlow.exchangeRateNote', { date: formatDateLocale(rateInfo.latest_timestamp) })}</strong>
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
      disabled={loading}
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
    <MetricCard label={t('cashFlow.totalInflows')} value={cashFlow.total_in} currencyCode={_displayCurrency} currencySymbol={_currencySymbol} tooltip={t('cashFlow.hintTotalInflows')} />
    <MetricCard label={t('cashFlow.totalOutflows')} value={cashFlow.total_out} currencyCode={_displayCurrency} currencySymbol={_currencySymbol} tooltip={t('cashFlow.hintTotalOutflows')} />
    <MetricCard
      label={t('cashFlow.netCashFlow')}
      value={cashFlow.net}
      currencyCode={_displayCurrency}
      currencySymbol={_currencySymbol}
      variant={cashFlow.net >= 0 ? 'positive' : 'negative'}
      tooltip={t('cashFlow.hintNetCashFlow')}
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
      <h2 class="section-title">{t('cashFlow.detail')} <InfoTip text={t('cashFlow.detailHint')} label={t('cashFlow.detail')} /></h2>

      <!-- Inflows group -->
      <div class="group-card">
        <button class="group-header inflow" onclick={() => toggleGroup('inflows')}>
          <span class="chevron" class:expanded={expandedGroups.has('inflows')}>▶</span>
          <span class="group-label">{t('cashFlow.inflows')}</span>
          <span class="group-amount inflow-amount">{_currencySymbol}{inflowTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </button>
        {#if expandedGroups.has('inflows')}
          <div class="group-body">
            {#each periodsForGroup(inflowLines) as period}
              {@const pKey = periodKey('inflows', period)}
              {@const pTotal = periodTotal(inflowLines, period)}
              <div class="period-row">
                <button class="period-header" onclick={() => togglePeriod(pKey)}>
                  <span class="chevron sm" class:expanded={expandedPeriods.has(pKey)}>▶</span>
                  <span class="period-label">{formatPeriod(period)}</span>
                  <span class="period-amount inflow-amount">{_currencySymbol}{pTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </button>
                {#if expandedPeriods.has(pKey)}
                  <div class="period-body">
                    {#each INFLOW_TYPES as txType}
                      {@const typeLines = inflowLines.filter(l => l.type === txType && l.period === period)}
                      {#each typeLines as line}
                        {@const key = typeKey(line)}
                        <div class="type-row">
                          <button class="type-header" onclick={() => { toggleType(key); loadTransactions(key, line); }}>
                            <span class="chevron sm" class:expanded={expandedTypes.has(key)}>▶</span>
                            <span class="type-label">{t(TYPE_LABELS[txType])}</span>
                            {#if line.category}
                              <span class="category-badge">{line.category}</span>
                            {/if}
                            <span class="type-currency">{line.currency}</span>
                            <span class="type-amount">{_currencySymbol}{line.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                            <span class="type-count">{line.count} {line.count === 1 ? t('cashFlow.transaction') : t('cashFlow.transactions')}</span>
                          </button>
                          {#if expandedTypes.has(key)}
                            <div class="tx-body">
                              {#if txLoading.has(key)}
                                <div class="tx-loading"><LoadingSpinner /></div>
                              {:else if txCache[key]?.transactions?.length > 0}
                                <table class="tx-table">
                                  <thead>
                                    <tr>
                                      <th>{t('common.date')}</th>
                                      <th>{t('cashFlow.source')}</th>
                                      <th>{t('common.description')}</th>
                                      <th class="num">{t('cashFlow.nativeAmount')}</th>
                                      <th class="num">{t('cashFlow.fxRate')}</th>
                                      <th class="num">{t('cashFlow.displayAmount', { currency: _currencySymbol })}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {#each txCache[key].transactions as tx (tx.id)}
                                      <tr>
                                        <td>{formatDateLocale(tx.date)}</td>
                                        <td class="source-cell">{tx.source || '—'}</td>
                                        <td class="desc-cell">{tx.description || '—'}</td>
                                        <td class="num">{getSymbolFor(tx.currency)}{formatAmount(tx.amount, tx.currency)}</td>
                                        <td class="num">
                                          {#if tx.rate !== null && tx.rate !== undefined}
                                            <span class="fx-pair">{getSymbolFor(line.currency)}→{getSymbolFor(_displayCurrency)}</span>{formatRate(tx.rate)}
                                          {:else}—{/if}
                                        </td>
                                        <td class="num">
                                          {#if tx.display_amount !== null && tx.display_amount !== undefined}
                                            {_currencySymbol}{formatAmount(tx.display_amount, _displayCurrency)}
                                          {:else}—{/if}
                                        </td>
                                      </tr>
                                    {/each}
                                  </tbody>
                                </table>
                                {#if txCache[key].total_count > 50}
                                  <div class="tx-more">
                                    <a href="/transactions?type={line.type}&currency={line.currency}&period={line.period}" class="tx-more-link">
                                      {t('cashFlow.viewAll', { count: txCache[key].total_count })}
                                    </a>
                                  </div>
                                {/if}
                              {:else}
                                <div class="tx-empty">{t('cashFlow.noTransactions')}</div>
                              {/if}
                            </div>
                          {/if}
                        </div>
                      {/each}
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Outflows group -->
      <div class="group-card">
        <button class="group-header outflow" onclick={() => toggleGroup('outflows')}>
          <span class="chevron" class:expanded={expandedGroups.has('outflows')}>▶</span>
          <span class="group-label">{t('cashFlow.outflows')}</span>
          <span class="group-amount outflow-amount">{_currencySymbol}{outflowTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </button>
        {#if expandedGroups.has('outflows')}
          <div class="group-body">
            {#each periodsForGroup(outflowLines) as period}
              {@const pKey = periodKey('outflows', period)}
              {@const pTotal = periodTotal(outflowLines, period)}
              <div class="period-row">
                <button class="period-header" onclick={() => togglePeriod(pKey)}>
                  <span class="chevron sm" class:expanded={expandedPeriods.has(pKey)}>▶</span>
                  <span class="period-label">{formatPeriod(period)}</span>
                  <span class="period-amount outflow-amount">{_currencySymbol}{pTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </button>
                {#if expandedPeriods.has(pKey)}
                  <div class="period-body">
                    {#each OUTFLOW_TYPES as txType}
                      {@const typeLines = outflowLines.filter(l => l.type === txType && l.period === period)}
                      {#each typeLines as line}
                        {@const key = typeKey(line)}
                        <div class="type-row">
                          <button class="type-header" onclick={() => { toggleType(key); loadTransactions(key, line); }}>
                            <span class="chevron sm" class:expanded={expandedTypes.has(key)}>▶</span>
                            <span class="type-label">{t(TYPE_LABELS[txType])}</span>
                            {#if line.category}
                              <span class="category-badge">{line.category}</span>
                            {/if}
                            <span class="type-currency">{line.currency}</span>
                            <span class="type-amount">{_currencySymbol}{line.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                            <span class="type-count">{line.count} {line.count === 1 ? t('cashFlow.transaction') : t('cashFlow.transactions')}</span>
                          </button>
                          {#if expandedTypes.has(key)}
                            <div class="tx-body">
                              {#if txLoading.has(key)}
                                <div class="tx-loading"><LoadingSpinner /></div>
                              {:else if txCache[key]?.transactions?.length > 0}
                                <table class="tx-table">
                                  <thead>
                                    <tr>
                                      <th>{t('common.date')}</th>
                                      <th>{t('cashFlow.source')}</th>
                                      <th>{t('common.description')}</th>
                                      <th class="num">{t('cashFlow.nativeAmount')}</th>
                                      <th class="num">{t('cashFlow.fxRate')}</th>
                                      <th class="num">{t('cashFlow.displayAmount', { currency: _currencySymbol })}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {#each txCache[key].transactions as tx (tx.id)}
                                      <tr>
                                        <td>{formatDateLocale(tx.date)}</td>
                                        <td class="source-cell">{tx.source || '—'}</td>
                                        <td class="desc-cell">{tx.description || '—'}</td>
                                        <td class="num">{getSymbolFor(tx.currency)}{formatAmount(tx.amount, tx.currency)}</td>
                                        <td class="num">
                                          {#if tx.rate !== null && tx.rate !== undefined}
                                            <span class="fx-pair">{getSymbolFor(line.currency)}→{getSymbolFor(_displayCurrency)}</span>{formatRate(tx.rate)}
                                          {:else}—{/if}
                                        </td>
                                        <td class="num">
                                          {#if tx.display_amount !== null && tx.display_amount !== undefined}
                                            {_currencySymbol}{formatAmount(tx.display_amount, _displayCurrency)}
                                          {:else}—{/if}
                                        </td>
                                      </tr>
                                    {/each}
                                  </tbody>
                                </table>
                                {#if txCache[key].total_count > 50}
                                  <div class="tx-more">
                                    <a href="/transactions?type={line.type}&currency={line.currency}&period={line.period}" class="tx-more-link">
                                      {t('cashFlow.viewAll', { count: txCache[key].total_count })}
                                    </a>
                                  </div>
                                {/if}
                              {:else}
                                <div class="tx-empty">{t('cashFlow.noTransactions')}</div>
                              {/if}
                            </div>
                          {/if}
                        </div>
                      {/each}
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
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

  /* Group cards (Inflows / Outflows) */
  .group-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    margin-bottom: var(--space-3);
    overflow: hidden;
  }

  .group-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: var(--space-4) var(--space-4);
    background: none;
    border: none;
    cursor: pointer;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    transition: background var(--transition-fast);
  }

  .group-header:hover {
    background: var(--color-surface-hover);
  }

  .group-header.inflow {
    border-left: 3px solid #2f9e44;
  }

  .group-header.outflow {
    border-left: 3px solid #e03131;
  }

  .group-label {
    flex: 1;
    text-align: left;
  }

  .group-amount {
    font-family: var(--font-mono);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
  }

  .inflow-amount { color: #2f9e44; }
  .outflow-amount { color: #e03131; }

  .group-body {
    border-top: 1px solid var(--color-border);
  }

  /* Period rows (Level 2) */
  .period-row {
    border-bottom: 1px solid var(--color-border);
  }

  .period-row:last-child {
    border-bottom: none;
  }

  .period-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4) var(--space-3) var(--space-6);
    background: none;
    border: none;
    cursor: pointer;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    transition: background var(--transition-fast);
  }

  .period-header:hover {
    background: var(--color-surface-hover);
  }

  .period-label {
    font-weight: var(--font-weight-medium);
  }

  .period-amount {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .period-body {
    border-top: 1px solid var(--color-border);
  }

  /* Chevron */
  .chevron {
    display: inline-block;
    font-size: 10px;
    transition: transform var(--transition-fast);
    color: var(--color-text-muted);
    width: 14px;
    text-align: center;
    flex-shrink: 0;
  }

  .chevron.expanded {
    transform: rotate(90deg);
  }

  .chevron.sm {
    font-size: 8px;
    width: 12px;
  }

  /* Type rows (Level 2) */
  .type-row {
    border-bottom: 1px solid var(--color-border);
  }

  .type-row:last-child {
    border-bottom: none;
  }

  .type-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4) var(--space-3) var(--space-8);
    background: none;
    border: none;
    cursor: pointer;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    transition: background var(--transition-fast);
  }

  .type-header:hover {
    background: var(--color-surface-hover);
  }

  .type-label {
    font-weight: var(--font-weight-medium);
  }

  .category-badge {
    background: var(--color-surface-alt);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: 0 var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .type-currency {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .type-amount {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    min-width: 80px;
    text-align: right;
  }

  .type-count {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    min-width: 100px;
    text-align: right;
  }

  /* Transaction body (Level 3) */
  .tx-body {
    padding: 0 var(--space-4) var(--space-3) var(--space-12);
    background: var(--color-surface-alt);
  }

  .tx-loading {
    display: flex;
    justify-content: center;
    padding: var(--space-3);
  }

  .tx-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: var(--space-4) 0;
    font-size: var(--font-size-xs);
  }

  .tx-table th {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  .tx-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .tx-table tr:last-child td {
    border-bottom: none;
  }

  .fx-pair {
    color: var(--color-text-muted);
    margin-right: var(--space-1);
  }

  .desc-cell {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .source-cell {
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--color-text-secondary);
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
  }

  .tx-more {
    padding: var(--space-2) var(--space-3);
    text-align: center;
  }

  .tx-more-link {
    font-size: var(--font-size-xs);
    color: var(--color-primary);
    text-decoration: none;
  }

  .tx-more-link:hover {
    text-decoration: underline;
  }

  .tx-empty {
    padding: var(--space-3);
    text-align: center;
    font-size: var(--font-size-xs);
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
</style>
