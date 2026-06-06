<script>
  import { onMount } from 'svelte';
  import { currenciesApi } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import StackedAreaChart from '$lib/components/charts/StackedAreaChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';

  let loading = $state(true);
  let error = $state(null);
  let syncing = $state(false);

  let codes = $state([]);

  let holdingsData = $state(null);
  let holdingsLoading = $state(false);

  let rateChartData = $state(null);
  let rateChartLoading = $state(false);

  let displayCurrency = $state('USD');
  let rateBaseCurrency = $state('USD');

  let holdingsPreset = $state('3m');
  let holdingsCustomStart = $state('');
  let holdingsCustomEnd = $state('');

  let ratePreset = $state('3m');
  let rateCustomStart = $state('');
  let rateCustomEnd = $state('');

  const PRESETS = [
    { key: '3m', label: '3 months' },
    { key: '6m', label: '6 months' },
    { key: '1y', label: '1 year' },
    { key: 'all', label: 'All' },
    { key: 'custom', label: 'Custom' },
  ];

  const CURRENCY_SYMBOLS = { USD: '$', EUR: '€', JPY: '¥', GBP: '£', CHF: 'CHF ' };

  function today() { return new Date(); }
  function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
  }
  function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function getRange(preset, customStart, customEnd) {
    if (preset === 'custom') {
      return { start: customStart || null, end: customEnd || null };
    }
    const now = today();
    switch (preset) {
      case '3m': return { start: formatDate(addMonths(now, -3)), end: formatDate(now) };
      case '6m': return { start: formatDate(addMonths(now, -6)), end: formatDate(now) };
      case '1y': return { start: formatDate(addMonths(now, -12)), end: formatDate(now) };
      case 'all': return { start: null, end: null };
      default: return { start: formatDate(addMonths(now, -3)), end: formatDate(now) };
    }
  }

  function formatCurrencyValue(value, currency) {
    if (value == null) return '-';
    const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
    const formatted = Math.abs(value) >= 1000000
      ? (value / 1000000).toFixed(2) + 'M'
      : Math.abs(value) >= 1000
        ? (value / 1000).toFixed(1) + 'K'
        : value.toFixed(2);
    return symbol + formatted;
  }

  async function loadCodes() {
    loading = true;
    error = null;
    try {
      codes = await currenciesApi.getList();
      if (!codes.includes(displayCurrency)) {
        displayCurrency = codes.includes('USD') ? 'USD' : (codes[0] || 'USD');
      }
      if (!codes.includes(rateBaseCurrency)) {
        rateBaseCurrency = codes.includes('USD') ? 'USD' : (codes[0] || 'USD');
      }
    } catch (e) {
      error = e.message || 'Failed to load currencies';
    } finally {
      loading = false;
    }
  }

  async function loadHoldings() {
    if (codes.length === 0) return;
    holdingsLoading = true;
    try {
      const range = getRange(holdingsPreset, holdingsCustomStart, holdingsCustomEnd);
      const start = range.start || formatDate(addMonths(today(), -3));
      const end = range.end || formatDate(today());
      holdingsData = await api.get(`/currencies/holdings?start_date=${start}&end_date=${end}&display_currency=${displayCurrency}`);
    } catch (e) {
      holdingsData = null;
    } finally {
      holdingsLoading = false;
    }
  }

  async function loadRateChart() {
    if (codes.length === 0) return;
    rateChartLoading = true;
    try {
      const range = getRange(ratePreset, rateCustomStart, rateCustomEnd);
      let url = `/currencies/rate-chart?base_currency=${rateBaseCurrency}`;
      if (range.start) url += `&start_date=${range.start}`;
      if (range.end) url += `&end_date=${range.end}`;
      rateChartData = await api.get(url);
    } catch (e) {
      rateChartData = null;
    } finally {
      rateChartLoading = false;
    }
  }

  async function loadAll() {
    await loadCodes();
    if (codes.length > 0) {
      await Promise.all([loadHoldings(), loadRateChart()]);
    }
  }

  function selectHoldingsPreset(key) {
    holdingsPreset = key;
    loadHoldings();
  }

  function selectRatePreset(key) {
    ratePreset = key;
    loadRateChart();
  }

  function handleDisplayCurrencyChange(newVal) {
    displayCurrency = newVal;
    loadHoldings();
  }

  function handleRateBaseChange(newVal) {
    rateBaseCurrency = newVal;
    loadRateChart();
  }

  async function handleSync() {
    syncing = true;
    error = null;
    try {
      await api.post('/currencies/sync');
      await loadAll();
    } catch (e) {
      error = e.message || 'Sync failed';
    } finally {
      syncing = false;
    }
  }

  onMount(loadAll);

  $effect(() => {
    if (codes.length > 0 && !codes.includes(displayCurrency)) {
      displayCurrency = codes.includes('USD') ? 'USD' : (codes[0] || 'USD');
    }
  });

  function getCardData() {
    if (!holdingsData || !holdingsData.latest_raw) return [];
    return codes.map(code => ({
      code,
      value: holdingsData.latest_raw[code] || 0,
    }));
  }

  function getStackedAreaDatasets() {
    if (!holdingsData || !holdingsData.series) return [];
    const colors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997'];
    return holdingsData.series.map((s, i) => ({
      label: s.currency,
      data: s.values,
      color: colors[i % colors.length],
    }));
  }

  function getRateChartDatasets() {
    if (!rateChartData || !rateChartData.datasets) return [];
    return rateChartData.datasets.map(d => ({
      label: d.label,
      data: d.data,
      axis: d.axis,
      color: d.color,
    }));
  }

  function getRateChartLabels() {
    if (!rateChartData || !rateChartData.labels) return [];
    return rateChartData.labels.map(l => {
      const d = new Date(l);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });
  }

  function getHoldingsChartLabels() {
    if (!holdingsData || !holdingsData.dates) return [];
    return holdingsData.dates.map(l => {
      const d = new Date(l);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });
  }
</script>

<div class="page-header">
  <h1 class="page-title">Currencies</h1>
  <div class="page-actions">
    <Button variant="secondary" size="sm" onclick={handleSync} disabled={syncing}>
      {syncing ? 'Syncing...' : 'Sync Rates'}
    </Button>
  </div>
</div>

<p class="seed-note">Pre-seeded currencies: USD, EUR, JPY</p>

{#if loading}
  <LoadingSpinner message="Loading currencies..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if codes.length === 0}
  <EmptyState title="No currencies yet" message="Currencies will be seeded on first startup." />
{:else}
  <div class="section">
    <h2 class="section-title">Total by Currency</h2>
    <div class="metric-grid">
      {#each getCardData() as card (card.code)}
        <MetricCard label={card.code} value={formatCurrencyValue(card.value, card.code)} />
      {/each}
    </div>
  </div>

  <div class="section">
    <h2 class="section-title">Holdings by Currency</h2>
    <div class="controls-row">
      <div class="control-group">
        <span class="control-label">Display:</span>
        <Select
          value={displayCurrency}
          options={codes.map(c => ({ value: c, label: c }))}
          onchange={(e) => handleDisplayCurrencyChange(e.target.value)}
        />
      </div>
    </div>
    <div class="preset-bar">
      {#each PRESETS as p (p.key)}
        <button
          class="preset-btn"
          class:active={holdingsPreset === p.key}
          onclick={() => selectHoldingsPreset(p.key)}
        >{p.label}</button>
      {/each}
      {#if holdingsPreset === 'custom'}
        <div class="custom-dates">
          <label>
            From
            <input type="date" bind:value={holdingsCustomStart} onchange={() => loadHoldings()} />
          </label>
          <label>
            To
            <input type="date" bind:value={holdingsCustomEnd} onchange={() => loadHoldings()} />
          </label>
        </div>
      {/if}
    </div>
    <ChartCard title="Holdings Over Time">
      {#if holdingsLoading}
        <LoadingSpinner message="Loading chart..." />
      {:else if getStackedAreaDatasets().length === 0}
        <p class="no-data">No holdings data available.</p>
      {:else}
        <StackedAreaChart
          labels={getHoldingsChartLabels()}
          datasets={getStackedAreaDatasets()}
        />
      {/if}
    </ChartCard>
  </div>

  <div class="section">
    <h2 class="section-title">Exchange Rates</h2>
    <div class="controls-row">
      <div class="control-group">
        <span class="control-label">Base:</span>
        <Select
          value={rateBaseCurrency}
          options={codes.map(c => ({ value: c, label: c }))}
          onchange={(e) => handleRateBaseChange(e.target.value)}
        />
      </div>
    </div>
    <div class="preset-bar">
      {#each PRESETS as p (p.key)}
        <button
          class="preset-btn"
          class:active={ratePreset === p.key}
          onclick={() => selectRatePreset(p.key)}
        >{p.label}</button>
      {/each}
      {#if ratePreset === 'custom'}
        <div class="custom-dates">
          <label>
            From
            <input type="date" bind:value={rateCustomStart} onchange={() => loadRateChart()} />
          </label>
          <label>
            To
            <input type="date" bind:value={rateCustomEnd} onchange={() => loadRateChart()} />
          </label>
        </div>
      {/if}
    </div>
    <ChartCard title="Exchange Rate History">
      {#if rateChartLoading}
        <LoadingSpinner message="Loading chart..." />
      {:else if getRateChartDatasets().length === 0}
        <p class="no-data">No rate data available. Try syncing rates first.</p>
      {:else}
        <LineChart
          labels={getRateChartLabels()}
          datasets={getRateChartDatasets()}
        />
      {/if}
    </ChartCard>
  </div>
{/if}

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-2);
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

  .seed-note {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0 0 var(--space-4) 0;
  }

  .section {
    margin-bottom: var(--space-6);
  }

  .section-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    margin: 0 0 var(--space-3) 0;
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .controls-row {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
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

  .preset-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
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

  .no-data {
    text-align: center;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    padding: var(--space-6);
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
