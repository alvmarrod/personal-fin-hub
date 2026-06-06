<script>
  import { onMount } from 'svelte';
  import { analytics, crud } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import MetricCard from '$lib/components/MetricCard.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import StackedBarChart from '$lib/components/charts/StackedBarChart.svelte';
  import Button from '$lib/components/Button.svelte';
  import AddIncomeModal from '$lib/components/modals/AddIncomeModal.svelte';
  import EditScheduleModal from '$lib/components/modals/EditScheduleModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';

  let loading = $state(true);
  let error = $state(null);
  let addModalOpen = $state(false);
  let editSchedule = $state(null);
  let deleteSchedule = $state(null);

  let activePreset = $state('6m');
  let customStart = $state('');
  let customEnd = $state('');

  let thisMonthRealized = $state(0);
  let thisMonthProjected = $state(0);
  let nextMonthIncome = $state(0);
  let projectedRangeTotal = $state(0);
  let activeSources = $state(0);

  let incomeChartLabels = $state([]);
  let incomeChartDatasets = $state([]);

  let incomeSources = $state([]);
  let recentIncome = $state([]);
  let dividendTxns = $state([]);

  const PRESETS = [
    { key: '3m', label: '3 months' },
    { key: '6m', label: '6 months' },
    { key: '1y', label: '1 year' },
    { key: 'past', label: 'Past year' },
    { key: 'all', label: 'All' },
    { key: 'custom', label: 'Custom' },
  ];

  function today() { return new Date(); }
  function parseISO(s) { if (!s) return null; const d = new Date(s); return isNaN(d.getTime()) ? null : d; }
  function parseNum(val) { const n = Number(val); return isNaN(n) ? 0 : n; }

  function startOfMonth(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }
  function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
  }
  function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  function formatPeriod(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }

  function advance(d, periodicity) {
    const r = new Date(d);
    switch (periodicity) {
      case 'DAILY': r.setDate(r.getDate() + 1); break;
      case 'WEEKLY': r.setDate(r.getDate() + 7); break;
      case 'MONTHLY': r.setMonth(r.getMonth() + 1); break;
      case 'QUARTERLY': r.setMonth(r.getMonth() + 3); break;
      case 'ANNUALLY': r.setFullYear(r.getFullYear() + 1); break;
    }
    return r;
  }

  function getMonthRange() {
    const now = today();
    return { start: formatDate(startOfMonth(now)), end: formatDate(now) };
  }

  function getChartRange() {
    if (activePreset === 'custom') {
      return { start: customStart || null, end: customEnd || null };
    }
    const now = today();
    switch (activePreset) {
      case '3m':  return { start: formatDate(now), end: formatDate(addMonths(now, 3)) };
      case '6m':  return { start: formatDate(now), end: formatDate(addMonths(now, 6)) };
      case '1y':  return { start: formatDate(now), end: formatDate(addMonths(now, 12)) };
      case 'past': return { start: formatDate(addMonths(now, -12)), end: formatDate(now) };
      case 'all':  return { start: null, end: null };
      default:     return { start: formatDate(now), end: formatDate(addMonths(now, 6)) };
    }
  }

  function generatePeriodLabels(start, end) {
    const startD = parseISO(start) || today();
    const endD = parseISO(end) || addMonths(today(), 6);
    const labels = [];
    const d = startOfMonth(startD);
    const endMonth = startOfMonth(endD);
    while (d <= endMonth) {
      labels.push(formatPeriod(d));
      d.setMonth(d.getMonth() + 1);
    }
    return labels;
  }

  function generateOccurrences(scheduleStart, scheduleEnd, periodicity, rangeStart, rangeEnd) {
    if (periodicity === 'ONE_OFF' || periodicity === 'CUSTOM') return [];

    const dates = [];
    let current = advance(new Date(scheduleStart), periodicity);
    const rangeS = rangeStart ? new Date(rangeStart) : null;
    const rangeE = rangeEnd ? new Date(rangeEnd) : null;
    const maxEnd = (scheduleEnd && rangeE)
      ? new Date(Math.min(new Date(scheduleEnd).getTime(), rangeE.getTime()))
      : (scheduleEnd || rangeE);

    if (!maxEnd) return [];

    const effectiveStart = (rangeS && rangeS > today()) ? rangeS : today();

    while (current < effectiveStart) {
      current = advance(current, periodicity);
    }

    while (current <= maxEnd) {
      dates.push(new Date(current));
      current = advance(current, periodicity);
    }

    return dates;
  }

  function getNextPaymentDate(schedule) {
    const now = today();
    const startDate = parseISO(schedule.start_date);
    if (!startDate) return null;
    if (startDate >= now) return formatDate(startDate);
    if (schedule.periodicity_type === 'ONE_OFF' || schedule.periodicity_type === 'CUSTOM') return null;
    let current = advance(startDate, schedule.periodicity_type);
    let guard = 0;
    while (current < now && guard < 120) {
      current = advance(current, schedule.periodicity_type);
      guard++;
    }
    if (schedule.end_date && current > parseISO(schedule.end_date)) return null;
    return formatDate(current);
  }

  function computeProjected(schedules, entityMap, rangeStart, rangeEnd) {
    const projected = [];
    for (const s of schedules || []) {
      if (s.entity_id == null || !['MONEY_IN', 'INTEREST', 'DIVIDEND'].includes(s.type)) continue;
      const occurrences = generateOccurrences(s.start_date, s.end_date, s.periodicity_type, rangeStart, rangeEnd);
      const entityName = entityMap[s.entity_id] || `Entity #${s.entity_id}`;
      const amount = parseNum(s.total_value);
      for (const d of occurrences) {
        projected.push({ period: formatPeriod(d), entity_id: s.entity_id, entity_name: entityName, total_value: amount });
      }
    }
    return projected;
  }

  function selectPreset(key) {
    activePreset = key;
    loadAll();
  }

  async function loadAll() {
    loading = true;
    error = null;
    try {
      const monthRange = getMonthRange();
      const chartRange = getChartRange();

      const [monthCf, sourceData, schedules, allTxns, entities] = await Promise.all([
        analytics.cashFlow({ groupBy: 'month', startDate: monthRange.start, endDate: monthRange.end }),
        analytics.incomeBySource({ groupBy: 'month', startDate: chartRange.start, endDate: chartRange.end }),
        crud.schedules.getList(),
        crud.transactions.getList(),
        crud.entities.getList(),
      ]);

      const entityMap = {};
      for (const e of entities || []) {
        entityMap[e.id] = e.name;
      }

      const incomeSchedules = (schedules || []).filter(s =>
        s.entity_id != null && ['MONEY_IN', 'INTEREST', 'DIVIDEND'].includes(s.type)
      );

      const projectedData = computeProjected(incomeSchedules, entityMap, chartRange.start, chartRange.end);

      // Realized this month (cash flow for current month)
      const realizedThisMonth = (monthCf.lines || [])
        .filter(l => ['MONEY_IN', 'INTEREST', 'DIVIDEND'].includes(l.type))
        .reduce((s, l) => s + l.total_value, 0);

      const currentMonthKey = formatPeriod(today());
      const nextMonthKey = formatPeriod(addMonths(today(), 1));

      const projectedThisMonth = projectedData
        .filter(p => p.period === currentMonthKey)
        .reduce((s, p) => s + p.total_value, 0);

      const projectedNextMonth = projectedData
        .filter(p => p.period === nextMonthKey)
        .reduce((s, p) => s + p.total_value, 0);

      const projectedInRange = projectedData.reduce((s, p) => s + p.total_value, 0);

      // Metric cards
      thisMonthRealized = realizedThisMonth;
      thisMonthProjected = projectedThisMonth;
      nextMonthIncome = projectedNextMonth;
      projectedRangeTotal = projectedInRange;
      activeSources = incomeSchedules.length;

      // Separate realized vs projected maps
      const realizedMap = {};
      for (const row of sourceData || []) {
        if (!realizedMap[row.entity_name]) realizedMap[row.entity_name] = {};
        realizedMap[row.entity_name][row.period] = (realizedMap[row.entity_name][row.period] || 0) + row.total_value;
      }

      const projectedMap = {};
      for (const proj of projectedData) {
        if (!projectedMap[proj.entity_name]) projectedMap[proj.entity_name] = {};
        projectedMap[proj.entity_name][proj.period] = (projectedMap[proj.entity_name][proj.period] || 0) + proj.total_value;
      }

      // Chart labels
      if (chartRange.start && chartRange.end) {
        incomeChartLabels = generatePeriodLabels(chartRange.start, chartRange.end);
      } else {
        const allPeriods = [...new Set([
          ...(sourceData || []).map(r => r.period),
          ...projectedData.map(p => p.period),
        ])].sort();
        incomeChartLabels = allPeriods;
      }

      const sourceNames = [...new Set([
        ...Object.keys(realizedMap),
        ...Object.keys(projectedMap),
      ])].sort();

      // Datasets: realized first (pastel blues), projected after (pastel greens)
      const realizedHue = 210;
      const projectedHue = 140;
      const n = Math.max(sourceNames.length, 1);
      const lightStep = 10 / n;
      incomeChartDatasets = sourceNames.flatMap((name, i) => [
        {
          label: `${name} (Realized)`,
          data: incomeChartLabels.map(p => realizedMap[name]?.[p] || 0),
          color: `hsl(${realizedHue}, 50%, ${76 + i * lightStep}%)`,
        },
        {
          label: `${name} (Projected)`,
          data: incomeChartLabels.map(p => projectedMap[name]?.[p] || 0),
          color: `hsl(${projectedHue}, 45%, ${76 + i * lightStep}%)`,
        },
      ]);

      // Income Sources: separate realized/projected per source
      incomeSources = sourceNames.map(name => {
        const realizedMonth = realizedMap[name]?.[currentMonthKey] || 0;
        const projectedMonth = projectedMap[name]?.[currentMonthKey] || 0;
        const allPeriods = [...new Set([
          ...Object.keys(realizedMap[name] || {}),
          ...Object.keys(projectedMap[name] || {}),
        ])];
        const total = allPeriods.reduce((s, p) => s + (realizedMap[name]?.[p] || 0) + (projectedMap[name]?.[p] || 0), 0);
        const schedule = incomeSchedules.find(s => entityMap[s.entity_id] === name);
        return { name, realized: realizedMonth, projected: projectedMonth, total, schedule, nextPayment: schedule ? getNextPaymentDate(schedule) : null };
      });

      // Recent income (excluding dividends)
      const allIncomeTxns = (allTxns || [])
        .filter(t => ['MONEY_IN', 'INTEREST', 'DIVIDEND'].includes(t.type))
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      recentIncome = allIncomeTxns.filter(t => t.type !== 'DIVIDEND').slice(0, 20);
      dividendTxns = allIncomeTxns.filter(t => t.type === 'DIVIDEND').slice(0, 20);
    } catch (e) {
      error = e.message || 'Failed to load income data';
    } finally {
      loading = false;
    }
  }

  onMount(loadAll);
</script>

<div class="page-header">
  <h1 class="page-title">Income</h1>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>+ Add Income</Button>
  </div>
</div>

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
        From
        <input type="date" bind:value={customStart} onchange={() => loadAll()} />
      </label>
      <label>
        To
        <input type="date" bind:value={customEnd} onchange={() => loadAll()} />
      </label>
    </div>
  {/if}
</div>

{#if loading}
  <LoadingSpinner message="Loading income data..." />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>Retry</Button>
  </div>
{:else if incomeChartDatasets.length === 0 && thisMonthRealized === 0 && thisMonthProjected === 0 && activeSources === 0 && recentIncome.length === 0 && dividendTxns.length === 0}
  <EmptyState title="No income data yet" message="Add your first income schedule or transaction to get started." />
{:else}
  <div class="metric-grid">
    <MetricCard label="Realized This Month" value={thisMonthRealized.toLocaleString()} />
    <MetricCard label="Projected This Month" value={thisMonthProjected.toLocaleString()} />
    <MetricCard label="Next Month" value={nextMonthIncome.toLocaleString()} />
    <MetricCard label="Projected (Range)" value={projectedRangeTotal.toLocaleString()} />
    <MetricCard label="Active Sources" value={String(activeSources)} />
  </div>

  <div class="chart-section">
    <ChartCard title="Income by Source">
      <StackedBarChart labels={incomeChartLabels} datasets={incomeChartDatasets} />
    </ChartCard>
  </div>

  {#if incomeSources.length > 0}
    <div class="table-section">
      <h2 class="section-title">Income Sources</h2>
      <div class="table-wrap">
        <table class="income-table">
          <thead>
            <tr>
              <th>Source</th>
              <th class="num">Realized</th>
              <th class="num">Projected</th>
              <th class="num">Total</th>
              <th>Schedule</th>
              <th>Next Payment</th>
              <th class="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each incomeSources as source (source.name)}
              <tr>
                <td class="cell-source">{source.name}</td>
                <td class="num">{source.realized.toLocaleString()}</td>
                <td class="num">{source.projected.toLocaleString()}</td>
                <td class="num">{source.total.toLocaleString()}</td>
                <td>
                  {#if source.schedule}
                    {source.schedule.description} ({source.schedule.periodicity_type})
                  {:else}
                    <span class="no-schedule">—</span>
                  {/if}
                </td>
                <td>{source.nextPayment || '-'}</td>
                <td>
                  {#if source.schedule}
                    <button class="icon-btn" title="Edit schedule" onclick={() => editSchedule = source.schedule}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="icon-btn icon-btn-danger" title="Delete schedule" onclick={() => deleteSchedule = source.schedule}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  {#if recentIncome.length > 0}
    <div class="table-section">
      <h2 class="section-title">Recent Income Transactions</h2>
      <div class="table-wrap">
        <table class="income-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Source</th>
              <th class="num">Amount</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {#each recentIncome as tx (tx.id)}
              <tr>
                <td>{new Date(tx.timestamp).toLocaleDateString()}</td>
                <td>{tx.type}</td>
                <td>{entityMap[tx.entity_id] || tx.entity_id}</td>
                <td class="num">{parseNum(tx.total_value).toLocaleString()}</td>
                <td class="cell-notes">{tx.notes || '-'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  {#if dividendTxns.length > 0}
    <div class="table-section">
      <h2 class="section-title">Dividends</h2>
      <div class="table-wrap">
        <table class="income-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Source</th>
              <th class="num">Amount</th>
              <th>Currency</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {#each dividendTxns as tx (tx.id)}
              <tr>
                <td>{new Date(tx.timestamp).toLocaleDateString()}</td>
                <td>{entityMap[tx.entity_id] || tx.entity_id}</td>
                <td class="num">{parseNum(tx.total_value).toLocaleString()}</td>
                <td>{tx.currency || '-'}</td>
                <td class="cell-notes">{tx.notes || '-'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
{/if}

<AddIncomeModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} />
<EditScheduleModal open={editSchedule !== null} schedule={editSchedule} onclose={() => editSchedule = null} onsuccess={loadAll} />
<ConfirmDeleteModal
  open={deleteSchedule !== null}
  title="Delete Schedule"
  message={deleteSchedule ? `Are you sure you want to delete "${deleteSchedule.description}"? This will stop future recurrences but will NOT delete past transactions.` : ''}
  onconfirm={async () => {
    if (!deleteSchedule) return;
    await api.del(`/schedules/${deleteSchedule.id}`);
    deleteSchedule = null;
    loadAll();
  }}
  oncancel={() => deleteSchedule = null}
/>

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
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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

  .income-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .income-table th {
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

  .income-table th.num {
    text-align: right;
  }

  .income-table th.actions-col {
    width: 80px;
    text-align: center;
  }

  .income-table td {
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

  .cell-source {
    font-weight: var(--font-weight-medium);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-muted);
  }

  .no-schedule {
    color: var(--color-text-muted);
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    color: var(--color-text-secondary);
    transition: background var(--transition-fast), color var(--transition-fast);
    vertical-align: middle;
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
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
