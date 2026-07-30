<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { t } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import { dashboard as dashboardTutorial } from '$lib/tutorial/definitions/index';
  import dashboardMock from '$lib/tutorial/mocks/dashboard';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';

  tutorialStore.registerMock('dashboard', dashboardMock);
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import DoughnutChart from '$lib/components/charts/DoughnutChart.svelte';
  import PieChart from '$lib/components/charts/PieChart.svelte';
  import CrossTabTable from '$lib/components/CrossTabTable.svelte';
  import GroupedTable from '$lib/components/GroupedTable.svelte';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import AddAssetModal from '$lib/components/modals/AddAssetModal.svelte';
  import AddIncomeModal from '$lib/components/modals/AddIncomeModal.svelte';

  let loading = $state(true);
  let error = $state(null);

  let dashboard = $state(null);
  let historical = $state({ labels: [], values: [], investmentValues: [] });
  let entityAlloc = $state({ labels: [], values: [] });
  let assetClassAlloc = $state({ labels: [], values: [] });
  let holdingsByEntity = $state([]);

  let addAssetOpen = $state(false);
  let addIncomeOpen = $state(false);

  let currencyCodes = $state([]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let unrealizedPLPct = $derived((dashboard?.total_invested ?? 0) > 0
    ? +(((dashboard?.unrealized_pl ?? 0) / dashboard.total_invested) * 100).toFixed(2)
    : 0);

  let realizedPLPct = $derived((dashboard?.total_invested ?? 0) > 0
    ? +(((dashboard?.realized_pl ?? 0) / dashboard.total_invested) * 100).toFixed(2)
    : 0);

  let portfolioChange = $derived(historical.values.length > 1
    ? historical.values[historical.values.length - 1] - historical.values[0]
    : null);
  let portfolioChangePct = $derived(historical.values.length > 1 && historical.values[0] !== 0
    ? +(((historical.values[historical.values.length - 1] - historical.values[0]) / Math.abs(historical.values[0])) * 100).toFixed(2)
    : null);

  let histChangeLabel = $derived(PRESETS.find(p => p.value === histPreset)?.label ?? '');

  let chartColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'];

  let histPreset = $state('1y');
  let histCustomStart = $state('');
  let histCustomEnd = $state('');

  let PRESETS = $derived([
    { value: '3m', label: t('common.presetShort3m') },
    { value: '6m', label: t('common.presetShort6m') },
    { value: '1y', label: t('common.presetShort1y') },
    { value: 'all', label: t('common.presetAll') },
    { value: 'custom', label: t('common.custom') },
  ]);

  function today() { return new Date(); }
  function addMonths(d, n) { const r = new Date(d); r.setMonth(r.getMonth() + n); return r; }
  function fmtDate(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

  function getHistRange() {
    const now = today();
    switch (histPreset) {
      case '3m': return { start: fmtDate(addMonths(now, -3)), end: fmtDate(now) };
      case '6m': return { start: fmtDate(addMonths(now, -6)), end: fmtDate(now) };
      case '1y': return { start: fmtDate(addMonths(now, -12)), end: fmtDate(now) };
      case 'all': return { start: null, end: null };
      case 'custom': return { start: histCustomStart || fmtDate(addMonths(now, -12)), end: histCustomEnd || fmtDate(now) };
      default: return { start: null, end: null };
    }
  }

  async function loadHistorical() {
    try {
      const range = getHistRange();
      const hist = await analytics.historical(
        range.start || '2020-01-01',
        range.end || new Date().toISOString().split('T')[0],
        'month', null, _displayCurrency
      );
      historical = {
        labels: (hist || []).map(h => h.date),
        values: (hist || []).map(h => h.total_value),
        investmentValues: (hist || []).map(h => h.investment_value ?? 0),
      };
    } catch (_) {}
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [dash, entityAllocData, assetClassAllocData, holdingsData, holdingsDataNative] = await Promise.all([
        analytics.dashboard(_displayCurrency),
        analytics.allocation('entity', _displayCurrency),
        analytics.allocation('asset_class', _displayCurrency),
        analytics.holdingsByEntity(_displayCurrency),
        analytics.holdingsByEntity(),
      ]);

      dashboard = dash;
      entityAlloc = {
        labels: (entityAllocData || []).map(a => a.category),
        values: (entityAllocData || []).map(a => a.value_abs),
      };
      assetClassAlloc = {
        labels: (assetClassAllocData || []).map(a => a.category),
        values: (assetClassAllocData || []).map(a => a.value_abs),
      };
      holdingsByEntity = holdingsData || [];

      // Build unified amount map: keyed by (entity_name, asset_class, currency)
      const unifiedMap = new Map();
      for (const h of (holdingsData || [])) {
        unifiedMap.set(`${h.entity_name}|${h.asset_class}|${h.currency || ''}`, h.current_value);
      }

      groupedRows = [];
      for (const h of (holdingsDataNative || [])) {
        const key = `${h.entity_name}|${h.asset_class}|${h.currency || ''}`;
        const convertedValue = unifiedMap.get(key) ?? h.current_value;
        groupedRows.push({
          entity: h.entity_name,
          assetClass: h.asset_class,
          origAmount: h.current_value,
          origCurrency: h.currency || displayCurrency,
          unifiedAmount: convertedValue,
        });
      }
    } catch (e) {
      error = e.message || 'Failed to load dashboard';
    } finally {
      loading = false;
    }
  }

  let groupedRows = $state([]);

  onMount(async () => {
    const shouldStart = !tutorialStore.isPageSeen('dashboard');
    if (shouldStart) {
      await tutorialStore.start('dashboard');
    }

    try {
      currencyCodes = await api.get('/currencies');
    } catch (_) {}
    await loadAll();
    loadHistorical();
  });
</script>

<div class="page-header">
  <h1 class="page-title">{t('dashboard.title')}</h1>
  <div class="page-actions">
    {#if currencyCodes.length > 0}
      <Select
        value={_displayCurrency}
        options={currencyCodes.map(c => ({ value: c, label: c }))}
        onchange={(e) => { setDisplayCurrency(e.target.value); loadAll().then(() => loadHistorical()); }}
      />
    {/if}
    <Button variant="primary" size="sm" onclick={() => addAssetOpen = true}>{t('dashboard.addAsset')}</Button>
    <Button variant="outline" size="sm" onclick={() => addIncomeOpen = true}>{t('dashboard.addIncome')}</Button>
    <ReplayButton page="dashboard" />
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('dashboard.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{t('common.errorPrefix', { resource: 'dashboard' })} {error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if dashboard}
  <div class="metric-grid">
    <MetricCard label={t('dashboard.portfolioValue')} value={dashboard.total_portfolio_value} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} />
    <MetricCard label={t('dashboard.cashBalance')} value={dashboard.cash_balance} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} />
    <MetricCard label={t('dashboard.totalInvested')} value={dashboard.investment_value} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} />
    <MetricCard
      label={t('dashboard.unrealizedPL')}
      value={dashboard?.unrealized_pl ?? 0}
      change={unrealizedPLPct}
      variant={unrealizedPLPct >= 0 ? 'positive' : 'negative'}
      changeLabel={t('dashboard.allTime')}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
    />
    <MetricCard
      label={t('dashboard.realizedPL')}
      value={dashboard?.realized_pl ?? 0}
      change={realizedPLPct}
      variant={realizedPLPct >= 0 ? 'positive' : 'negative'}
      changeLabel={t('dashboard.allTime')}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
    />
    <MetricCard
      label={t('dashboard.portfolioChange')}
      value={portfolioChange !== null ? portfolioChange : null}
      change={portfolioChangePct}
      variant={portfolioChangePct !== null ? (portfolioChangePct >= 0 ? 'positive' : 'negative') : 'neutral'}
      changeLabel={histChangeLabel}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
    />
  </div>

  <div class="charts-grid">
    <div class="chart-col-wide">
      <div class="date-presets">
        {#each PRESETS as preset}
          <button
            class="preset-btn"
            class:active={histPreset === preset.value}
            onclick={() => { histPreset = preset.value; loadHistorical(); }}
          >{preset.label}</button>
        {/each}
        {#if histPreset === 'custom'}
          <TextInput type="date" placeholder={t('common.start')} value={histCustomStart} oninput={(e) => { histCustomStart = e.target.value; loadHistorical(); }} />
          <span class="custom-sep">—</span>
          <TextInput type="date" placeholder={t('common.end')} value={histCustomEnd} oninput={(e) => { histCustomEnd = e.target.value; loadHistorical(); }} />
        {/if}
      </div>
      <ChartCard title={t('dashboard.historicalValue')}>
        <LineChart labels={historical.labels} datasets={[
          { data: historical.values, label: t('dashboard.portfolioValue') },
          { data: historical.investmentValues, label: t('dashboard.investmentValue') },
        ]} currencySymbol={_currencySymbol} />
      </ChartCard>
    </div>
  </div>

  <div class="charts-grid charts-grid-half">
    <ChartCard title={t('dashboard.byEntity')}>
      <DoughnutChart labels={entityAlloc.labels} data={entityAlloc.values} colors={chartColors} currencySymbol={_currencySymbol} />
    </ChartCard>
    <ChartCard title={t('dashboard.byAssetClass')}>
      <PieChart labels={assetClassAlloc.labels} data={assetClassAlloc.values} colors={chartColors} currencySymbol={_currencySymbol} />
    </ChartCard>
  </div>

  <div class="table-section">
    <ChartCard title={t('dashboard.assetClassEntityTable')}>
      <GroupedTable rows={groupedRows} currencySymbol={_currencySymbol} />
    </ChartCard>
  </div>
{:else}
  <EmptyState title={t('dashboard.emptyTitle')} message={t('dashboard.emptyMsg')} />
{/if}

<TutorialOverlay definition={dashboardTutorial} onfinish={loadAll} />

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
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .metric-grid :global(.metric-value) {
    font-size: var(--font-size-xl);
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

  .date-presets {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
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
</style>
