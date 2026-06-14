<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import DoughnutChart from '$lib/components/charts/DoughnutChart.svelte';
  import PieChart from '$lib/components/charts/PieChart.svelte';
  import CrossTabTable from '$lib/components/CrossTabTable.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import AddAssetModal from '$lib/components/modals/AddAssetModal.svelte';
  import AddIncomeModal from '$lib/components/modals/AddIncomeModal.svelte';

  let loading = $state(true);
  let error = $state(null);

  let dashboard = $state(null);
  let historical = $state({ labels: [], values: [] });
  let entityAlloc = $state({ labels: [], values: [] });
  let assetClassAlloc = $state({ labels: [], values: [] });
  let holdingsByEntity = $state([]);

  let addAssetOpen = $state(false);
  let addIncomeOpen = $state(false);

  let displayCurrency = $state('USD');
  let currencyCodes = $state([]);

  const CURRENCY_SYMBOLS = { USD: '$', EUR: '€', JPY: '¥', GBP: '£' };

  let currencySymbol = $derived(CURRENCY_SYMBOLS[displayCurrency] ?? displayCurrency + ' ');

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'];

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

      const [dash, hist, entityAllocData, assetClassAllocData, holdingsData] = await Promise.all([
        analytics.dashboard(displayCurrency),
        analytics.historical(startDate, endDate, 'month', null, displayCurrency),
        analytics.allocation('entity', displayCurrency),
        analytics.allocation('asset_class', displayCurrency),
        analytics.holdingsByEntity(displayCurrency),
      ]);

      dashboard = dash;
      historical = {
        labels: (hist || []).map(h => h.date),
        values: (hist || []).map(h => h.total_value),
      };
      entityAlloc = {
        labels: (entityAllocData || []).map(a => a.category),
        values: (entityAllocData || []).map(a => a.value_abs),
      };
      assetClassAlloc = {
        labels: (assetClassAllocData || []).map(a => a.category),
        values: (assetClassAllocData || []).map(a => a.value_abs),
      };
      holdingsByEntity = holdingsData || [];
    } catch (e) {
      error = e.message || 'Failed to load dashboard';
    } finally {
      loading = false;
    }
  }

  function getCrossTabCell(assetClass, entityName) {
    return holdingsByEntity
      .filter(h => h.entity_name === entityName && h.asset_class === assetClass)
      .reduce((sum, h) => sum + h.current_value, 0);
  }

  let entityNames = $derived([...new Set(holdingsByEntity.map(h => h.entity_name))]);
  let assetClasses = $derived([...new Set(holdingsByEntity.map(h => h.asset_class))]);

  onMount(async () => {
    try {
      currencyCodes = await api.get('/currencies');
    } catch (_) {}
    loadAll();
  });
</script>

<div class="page-header">
  <h1 class="page-title">Dashboard</h1>
  <div class="page-actions">
    {#if currencyCodes.length > 0}
      <Select
        value={displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { displayCurrency = e.target.value; loadAll(); }}
      />
    {/if}
    <Button variant="primary" size="sm" onclick={() => addAssetOpen = true}>+ Add Asset</Button>
    <Button variant="outline" size="sm" onclick={() => addIncomeOpen = true}>+ Add Income</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message="Loading dashboard..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">Failed to load dashboard: {error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if dashboard}
  <div class="metric-grid">
    <MetricCard label="Portfolio Value" value={dashboard.total_portfolio_value?.toLocaleString()} currencySymbol={currencySymbol} />
    <MetricCard label="Cash Balance" value={dashboard.cash_balance?.toLocaleString()} currencySymbol={currencySymbol} />
    <MetricCard label="Total Invested" value={dashboard.total_invested?.toLocaleString()} currencySymbol={currencySymbol} />
    <MetricCard
      label="Total Return"
      value={`${dashboard.total_return_pct?.toFixed(2) ?? '0.00'}%`}
      change={dashboard.total_return_pct ?? 0}
      variant={dashboard.total_return_pct >= 0 ? 'positive' : 'negative'}
      changeLabel="all time"
    />
  </div>

  <div class="charts-grid">
    <div class="chart-col-wide">
      <ChartCard title="Historical Portfolio Value">
        <LineChart labels={historical.labels} datasets={[{ data: historical.values, label: 'Portfolio Value' }]} currencySymbol={currencySymbol} />
      </ChartCard>
    </div>
  </div>

  <div class="charts-grid charts-grid-half">
    <ChartCard title="By Entity">
      <DoughnutChart labels={entityAlloc.labels} data={entityAlloc.values} colors={chartColors} currencySymbol={currencySymbol} />
    </ChartCard>
    <ChartCard title="By Asset Class">
      <PieChart labels={assetClassAlloc.labels} data={assetClassAlloc.values} colors={chartColors} currencySymbol={currencySymbol} />
    </ChartCard>
  </div>

  <div class="table-section">
    <ChartCard title="Asset Class x Entity Summary">
      <CrossTabTable
        rows={assetClasses}
        columns={entityNames}
        cellData={getCrossTabCell}
        rowLabel="Asset Class"
        colLabel="Entity"
        currencySymbol={currencySymbol}
      />
    </ChartCard>
  </div>
{:else}
  <EmptyState title="No data yet" message="Start by adding your first transaction." />
{/if}

<AddAssetModal open={addAssetOpen} onclose={() => addAssetOpen = false} onsuccess={loadAll} />
<AddIncomeModal open={addIncomeOpen} onclose={() => addIncomeOpen = false} onsuccess={loadAll} />

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

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .charts-grid {
    display: grid;
    gap: var(--space-5);
    margin-bottom: var(--space-5);
  }

  .chart-col-wide {
    grid-column: 1 / -1;
  }

  .charts-grid-half {
    grid-template-columns: 1fr 1fr;
  }

  .table-section {
    margin-bottom: var(--space-6);
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
    .charts-grid-half {
      grid-template-columns: 1fr;
    }

    .page-header {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--space-3);
    }
  }
</style>
