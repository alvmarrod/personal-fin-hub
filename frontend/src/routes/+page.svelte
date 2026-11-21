<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { t } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte';
  import { formatAmount } from '$lib/utils/format.svelte';
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
  import GroupedTable from '$lib/components/GroupedTable.svelte';
  import StrategyDeviationCard from '$lib/components/StrategyDeviationCard.svelte';
  import InfoButton from '$lib/components/InfoButton.svelte';
  import { currencyExposure } from '$lib/utils/exposure.js';
  import Button from '$lib/components/Button.svelte';
  import Select from '$lib/components/Select.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import AddAssetModal from '$lib/components/modals/AddAssetModal.svelte';
  import AddIncomeModal from '$lib/components/modals/AddIncomeModal.svelte';

  let loading = $state(true);
  let histLoading = $state(false);
  let error = $state(null);

  let dashboard = $state(null);
  let historical = $state({ labels: [], values: [], investmentValues: [] });
  let currencyAlloc = $state({ labels: [], values: [], original: [], excluded: 0 });
  let strategyDrift = $state(null);

  let layerInfoItems = $derived([
    { label: t('modals.layerCore'), text: t('dashboard.layerInfoCore') },
    { label: t('modals.layerReserve'), text: t('dashboard.layerInfoReserve') },
    { label: t('modals.layerSatellite'), text: t('dashboard.layerInfoSatellite') },
  ]);

  let currencyTooltip = $derived(
    currencyAlloc.labels.map((code, index) =>
      code === _displayCurrency
        ? ''
        : t('dashboard.originalAmount', {
            amount: `${getSymbolFor(code)}${formatAmount(currencyAlloc.original[index] ?? 0)}`,
          }),
    ),
  );
  let layerAlloc = $state({ labels: [], values: [] });
  let layerAssigned = $state(true);

  const LAYER_KEYS = {
    core: 'layer.core',
    reserve: 'layer.reserve',
    satellite: 'layer.satellite',
    unspecified: 'layer.unspecified',
  };

  function layerLabel(value) {
    return t(LAYER_KEYS[value] ?? 'layer.unspecified');
  }

  let addAssetOpen = $state(false);
  let addIncomeOpen = $state(false);

  let currencyCodes = $state([]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let unrealizedPLPct = $derived((dashboard?.total_invested ?? 0) > 0
    ? ((dashboard?.unrealized_pl ?? 0) / dashboard.total_invested) * 100
    : 0);

  let realizedPLPct = $derived((dashboard?.total_invested ?? 0) > 0
    ? ((dashboard?.realized_pl ?? 0) / dashboard.total_invested) * 100
    : 0);

  let portfolioChange = $derived(historical.values.length > 1
    ? historical.values[historical.values.length - 1] - historical.values[0]
    : null);
  let portfolioChangePct = $derived(historical.values.length > 1 && historical.values[0] !== 0
    ? ((historical.values[historical.values.length - 1] - historical.values[0]) / Math.abs(historical.values[0])) * 100
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
    histLoading = true;
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
    } catch (_) {} finally {
      histLoading = false;
    }
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const [dash, layerAllocData, holdingsData, holdingsDataNative, strategyDriftData] = await Promise.all([
        analytics.dashboard(_displayCurrency),
        analytics.allocation('layer', _displayCurrency),
        analytics.holdingsByEntity(_displayCurrency),
        analytics.holdingsByEntity(),
        api.get(`/strategy/drift?display_currency=${encodeURIComponent(_displayCurrency)}`).catch(() => null),
      ]);

      dashboard = dash;
      strategyDrift = strategyDriftData ?? null;
      const layers = layerAllocData || [];
      layerAssigned = layers.some(a => a.category !== 'unspecified');
      layerAlloc = {
        labels: layers.map(a => layerLabel(a.category)),
        values: layers.map(a => a.value_abs),
      };

      // Build unified amount map: keyed by (entity_name, asset_class, currency)
      const unifiedMap = new Map();
      for (const h of (holdingsData || [])) {
        unifiedMap.set(`${h.entity_name}|${h.asset_class}|${h.currency || ''}`, {
          value: h.current_value,
          rateMissing: !!h.rate_missing,
        });
      }

      groupedRows = [];
      for (const h of (holdingsDataNative || [])) {
        const key = `${h.entity_name}|${h.asset_class}|${h.currency || ''}`;
        const unified = unifiedMap.get(key);
        groupedRows.push({
          entity: h.entity_name,
          assetClass: h.asset_class,
          origAmount: h.current_value,
          origCurrency: h.currency || displayCurrency,
          unifiedAmount: unified?.value ?? h.current_value,
          rateMissing: unified?.rateMissing ?? false,
        });
      }
      currencyAlloc = currencyExposure(groupedRows);
    } catch (e) {
      error = e.message || 'Failed to load dashboard';
    } finally {
      loading = false;
    }
  }

  let groupedRows = $state([]);

  onMount(async () => {
    try {
      currencyCodes = await api.get('/currencies');
    } catch (_) {}
    await loadAll();
    loadHistorical();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('dashboard'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('dashboard');
    if (on && !_tutWasOn) loadAll().then(() => loadHistorical());
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('dashboard.title')}</h1>
    <ReplayButton page="dashboard" />
  </div>
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
    <MetricCard label={t('dashboard.portfolioValue')} value={dashboard.total_portfolio_value} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('dashboard.hintPortfolioValue')} />
    <MetricCard label={t('dashboard.cashBalance')} value={dashboard.cash_balance} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('dashboard.hintCashBalance')} />
    <MetricCard label={t('dashboard.totalInvested')} value={dashboard.investment_value} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} tooltip={t('dashboard.hintInvested')} />
    <MetricCard
      label={t('dashboard.unrealizedPL')}
      value={dashboard?.unrealized_pl ?? 0}
      change={unrealizedPLPct}
      variant={unrealizedPLPct >= 0 ? 'positive' : 'negative'}
      changeLabel={t('dashboard.allTime')}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
      tooltip={t('dashboard.hintUnrealizedPL')}
    />
    <MetricCard
      label={t('dashboard.realizedPL')}
      value={dashboard?.realized_pl ?? 0}
      change={realizedPLPct}
      variant={realizedPLPct >= 0 ? 'positive' : 'negative'}
      changeLabel={t('dashboard.allTime')}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
      tooltip={t('dashboard.hintRealizedPL')}
    />
    <MetricCard
      label={t('dashboard.portfolioChange')}
      value={portfolioChange !== null ? portfolioChange : null}
      change={portfolioChangePct}
      variant={portfolioChangePct !== null ? (portfolioChangePct >= 0 ? 'positive' : 'negative') : 'neutral'}
      changeLabel={histChangeLabel}
      currencySymbol={_currencySymbol}
      currencyCode={_displayCurrency}
      tooltip={t('dashboard.hintPortfolioChange')}
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
            disabled={histLoading}
          >{preset.label}</button>
        {/each}
        {#if histPreset === 'custom'}
          <TextInput type="date" placeholder={t('common.start')} value={histCustomStart} oninput={(e) => { histCustomStart = e.target.value; loadHistorical(); }} />
          <span class="custom-sep">—</span>
          <TextInput type="date" placeholder={t('common.end')} value={histCustomEnd} oninput={(e) => { histCustomEnd = e.target.value; loadHistorical(); }} />
        {/if}
      </div>
      <ChartCard title={t('dashboard.historicalValue')}>
        {#if histLoading}
          <LoadingSpinner />
        {:else}
        <LineChart labels={historical.labels} datasets={[
          { data: historical.values, label: t('dashboard.portfolioValue') },
          { data: historical.investmentValues, label: t('dashboard.investmentValue') },
        ]} currencySymbol={_currencySymbol} />
        {/if}
      </ChartCard>
    </div>
  </div>

  <div class="charts-grid charts-grid-thirds">
    <ChartCard title={t('dashboard.byCurrency')}>
      {#if currencyAlloc.values.length > 0}
        <DoughnutChart labels={currencyAlloc.labels} data={currencyAlloc.values} colors={chartColors} currencySymbol={_currencySymbol} tooltipExtra={currencyTooltip} />
        {#if currencyAlloc.excluded > 0}
          <p class="chart-note">{t('dashboard.noRateNote', { count: currencyAlloc.excluded })}</p>
        {/if}
      {:else}
        <p class="chart-note">{t('common.noData')}</p>
      {/if}
    </ChartCard>
    <ChartCard title={t('dashboard.byLayer')}>
      {#snippet info()}
        <InfoButton
          title={t('dashboard.layerInfoTitle')}
          label={t('dashboard.layerInfoLabel')}
          items={layerInfoItems}
          note={t('dashboard.layerInfoUsage')}
        />
      {/snippet}
      {#if !layerAssigned}
        <p class="chart-note">{t('dashboard.noLayer')}</p>
      {:else if layerAlloc.values.length > 0}
        <PieChart labels={layerAlloc.labels} data={layerAlloc.values} colors={chartColors} currencySymbol={_currencySymbol} />
      {:else}
        <p class="chart-note">{t('common.noData')}</p>
      {/if}
    </ChartCard>
    <ChartCard title={t('dashboard.targetVsActual')}>
      <StrategyDeviationCard drift={strategyDrift} />
    </ChartCard>
  </div>

  <div class="table-section">
    <ChartCard title={t('dashboard.assetClassEntityTable')}>
      <GroupedTable rows={groupedRows} currencySymbol={_currencySymbol} currencyCode={_displayCurrency} />
    </ChartCard>
  </div>
{:else}
  <EmptyState title={t('dashboard.emptyTitle')} message={t('dashboard.emptyMsg')} />
{/if}

<TutorialOverlay definition={dashboardTutorial} onfinish={() => { loadAll().then(() => loadHistorical()); }} />

<AddAssetModal open={addAssetOpen} onclose={() => addAssetOpen = false} onsuccess={loadAll} />
<AddIncomeModal open={addIncomeOpen} onclose={() => addIncomeOpen = false} onsuccess={loadAll} />

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

  .charts-grid-thirds {
    grid-template-columns: repeat(3, 1fr);
  }

  .table-section {
    margin-bottom: var(--space-6);
  }

  .chart-note {
    margin: var(--space-2) 0 0;
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

  @media (max-width: 1100px) {
    .charts-grid-thirds {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 768px) {
    .charts-grid-thirds {
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
