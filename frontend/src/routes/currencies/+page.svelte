<script>
  import { onMount } from 'svelte';
  import { currenciesApi } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';

  let loading = $state(true);
  let error = $state(null);
  let syncing = $state(false);

  let codes = $state([]);
  let ratesMap = $state({});
  let currenciesLoading = $state(false);

  let selectedCode = $state(null);
  let historicalData = $state({ labels: [], values: [] });
  let historicalLoading = $state(false);

  let baseCurrency = $state('USD');
  let baseCurrencyOptions = $state([]);

  function formatRate(rate) {
    if (rate == null) return '-';
    return Number(rate).toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  }

  function formatTimestamp(ts) {
    if (!ts) return '-';
    return new Date(ts).toLocaleDateString();
  }

  async function loadCodes() {
    loading = true;
    error = null;
    try {
      codes = await currenciesApi.getList();
      baseCurrencyOptions = codes
        .filter(c => c !== selectedCode)
        .map(c => ({ value: c, label: c }));
      if (!baseCurrencyOptions.find(o => o.value === baseCurrency)) {
        baseCurrency = codes.includes('USD') ? 'USD' : (codes[0] || 'USD');
      }
    } catch (e) {
      error = e.message || 'Failed to load currencies';
    } finally {
      loading = false;
    }
  }

  async function loadRates() {
    currenciesLoading = true;
    const newMap = {};
    try {
      const results = await Promise.allSettled(
        codes.map(code =>
          currenciesApi.getLatestRate(code, baseCurrency)
            .then(r => ({ code, rate: r.rate, timestamp: r.timestamp }))
            .catch(() => ({ code, rate: null, timestamp: null }))
        )
      );
      for (const r of results) {
        if (r.status === 'fulfilled') {
          newMap[r.value.code] = { rate: r.value.rate, timestamp: r.value.timestamp };
        }
      }
      if (selectedCode && !newMap[selectedCode]) {
        selectedCode = null;
        historicalData = { labels: [], values: [] };
      }
    } finally {
      ratesMap = newMap;
      currenciesLoading = false;
    }
  }

  async function loadHistorical(code) {
    selectedCode = code;
    historicalLoading = true;
    try {
      const data = await currenciesApi.getRateHistory(code, baseCurrency);
      historicalData = {
        labels: (data || []).map(d => {
          const ts = new Date(d.timestamp);
          return ts.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
        }),
        values: (data || []).map(d => d.rate),
      };
    } catch {
      historicalData = { labels: [], values: [] };
    } finally {
      historicalLoading = false;
    }
  }

  function handleRowClick(code) {
    if (code === selectedCode) {
      selectedCode = null;
      historicalData = { labels: [], values: [] };
      return;
    }
    loadHistorical(code);
  }

  async function loadAll() {
    await loadCodes();
    if (codes.length > 0) await loadRates();
  }

  function handleBaseChange(newBase) {
    baseCurrency = newBase;
    selectedCode = null;
    historicalData = { labels: [], values: [] };
    if (codes.length > 0) loadRates();
  }

  function handleSync() {
    syncing = true;
    // Placeholder — sync implementation pending Market API currency rates
    setTimeout(() => { syncing = false; }, 600);
  }

  onMount(loadAll);

  $effect(() => {
    baseCurrencyOptions = codes
      .filter(c => c !== selectedCode)
      .map(c => ({ value: c, label: c }));
  });
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
  <div class="table-section">
    <div class="table-wrap">
      <table class="currency-table">
        <thead>
          <tr>
            <th>Code</th>
            <th class="num">Latest Rate <span class="rate-base">(vs {baseCurrency})</span></th>
            <th class="num">Last Updated</th>
          </tr>
        </thead>
        <tbody>
          {#each codes as code (code)}
            <tr
              class:selected={selectedCode === code}
              onclick={() => handleRowClick(code)}
              role="button"
              tabindex="0"
              onkeypress={(e) => e.key === 'Enter' && handleRowClick(code)}
            >
              <td class="cell-code">{code}</td>
              <td class="num">{currenciesLoading ? '...' : formatRate(ratesMap[code]?.rate)}</td>
              <td class="num muted">{currenciesLoading ? '...' : formatTimestamp(ratesMap[code]?.timestamp)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  {#if selectedCode}
    <div class="chart-section">
      <div class="chart-header">
        <ChartCard title="{selectedCode} / {baseCurrency} Historical Rate">
          <div class="base-picker">
            <span class="base-picker-label">Base:</span>
            <Select
              bind:value={baseCurrency}
              options={baseCurrencyOptions}
              onchange={(e) => handleBaseChange(e.target.value)}
            />
          </div>
          {#if historicalLoading}
            <LoadingSpinner message="Loading chart..." />
          {:else if historicalData.labels.length === 0}
            <p class="no-data">No rate data available for this pair.</p>
          {:else}
            <LineChart labels={historicalData.labels} data={historicalData.values} />
          {/if}
        </ChartCard>
      </div>
    </div>
  {/if}
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

  .currency-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .currency-table th {
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

  .currency-table th.num {
    text-align: right;
  }

  .currency-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .currency-table tbody tr {
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .currency-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .currency-table tbody tr.selected {
    background: var(--color-primary-bg);
    box-shadow: inset 3px 0 0 var(--color-primary);
  }

  .cell-code {
    font-weight: var(--font-weight-semibold);
    font-family: var(--font-mono);
    text-transform: uppercase;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .num.muted {
    color: var(--color-text-muted);
  }

  .rate-base {
    font-weight: var(--font-weight-normal);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .chart-section {
    margin-bottom: var(--space-6);
  }

  .chart-header {
    position: relative;
  }

  .base-picker {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .base-picker-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-medium);
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
