<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { formatDate, formatDateTime, formatAmount, maskAmount } from '$lib/utils/format.svelte';
  import { parseUtc } from '$lib/utils/time.js';
  import { getSymbolFor } from '$lib/preferences/currency.svelte';
  import { crud, analytics } from '$lib/api/analytics.js';
  import { api } from '$lib/api/client.js';
  import { LoadingSpinner, EmptyState, Pagination } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import ChartCard from '$lib/components/ChartCard.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import TextInput from '$lib/components/TextInput.svelte';
  import AddBalanceSnapshotModal from '$lib/components/modals/AddBalanceSnapshotModal.svelte';
  import EditBalanceSnapshotModal from '$lib/components/modals/EditBalanceSnapshotModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { balanceSnapshots as balanceSnapshotsTutorial } from '$lib/tutorial/definitions/index';
  import balanceSnapshotsMock from '$lib/tutorial/mocks/balance-snapshots';

  tutorialStore.registerMock('balance-snapshots', balanceSnapshotsMock);

  let loading = $state(true);
  let error = $state(null);
  let addModalOpen = $state(false);
  let editSnapshot = $state(null);
  let deleteSnapshot = $state(null);

  let snapshots = $state([]);
  let balances = $state([]);
  let entities = $state([]);
  let entityMap = $state({});

  let selectedEntity = $state(null);
  let expandedGroupId = $state(null);

  let currentPage = $state(1);
  const PER_PAGE = 20;

  // Cash-history chart controls (same presets as the dashboard).
  let chartPreset = $state('1y');
  let chartCustomStart = $state('');
  let chartCustomEnd = $state('');
  let chartLoading = $state(false);
  let chartError = $state(false);
  let chartPoints = $state([]);

  let PRESETS = $derived([
    { value: '3m', label: t('common.presetShort3m') },
    { value: '6m', label: t('common.presetShort6m') },
    { value: '1y', label: t('common.presetShort1y') },
    { value: 'all', label: t('common.presetAll') },
    { value: 'custom', label: t('common.custom') },
  ]);

  // One row per pocket: the derived cash plus the snapshots that anchor it.
  let groups = $derived.by(() => {
    const map = new Map();
    for (const b of balances) {
      if (selectedEntity !== null && b.entity_id !== selectedEntity) continue;
      const key = `${b.entity_id}||${b.currency}`;
      map.set(key, {
        key,
        entity_id: b.entity_id,
        currency: b.currency,
        current: b.balance,
        snapshots: [],
      });
    }
    for (const s of snapshots) {
      if (selectedEntity !== null && s.entity_id !== selectedEntity) continue;
      const key = `${s.entity_id}||${s.currency}`;
      if (!map.has(key)) {
        map.set(key, { key, entity_id: s.entity_id, currency: s.currency, current: 0, snapshots: [] });
      }
      map.get(key).snapshots.push(s);
    }
    const result = [...map.values()];
    for (const g of result) {
      g.snapshots.sort((a, b) => new Date(parseUtc(b.timestamp)) - new Date(parseUtc(a.timestamp)));
      g.last = g.snapshots[0] || null;
    }
    result.sort((a, b) => {
      const an = entityMap[a.entity_id] || '';
      const bn = entityMap[b.entity_id] || '';
      return an.localeCompare(bn) || a.currency.localeCompare(b.currency);
    });
    return result;
  });

  let chartGroup = $derived(groups.find((g) => g.key === expandedGroupId) || null);

  let totalPages = $derived(Math.ceil(groups.length / PER_PAGE));

  let paginatedGroups = $derived(groups.slice((currentPage - 1) * PER_PAGE, currentPage * PER_PAGE));

  function fmt(value, currency) {
    return `${maskAmount(formatAmount(value, currency))} ${getSymbolFor(currency)}`;
  }

  function ageDays(group) {
    if (!group.last) return null;
    const ms = Date.now() - new Date(parseUtc(group.last.timestamp)).getTime();
    return Math.max(0, Math.floor(ms / 86_400_000));
  }

  function ageVariant(days) {
    if (days === null) return null;
    if (days < 30) return 'success';
    if (days >= 120) return 'danger';
    if (days >= 90) return 'warning';
    if (days >= 60) return 'caution';
    return null;
  }

  function today() {
    return new Date();
  }

  function addMonths(d, n) {
    const r = new Date(d);
    r.setMonth(r.getMonth() + n);
    return r;
  }

  function fmtDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function rangeForPreset(group) {
    const now = today();
    switch (chartPreset) {
      case '3m':
        return { start: fmtDate(addMonths(now, -3)), end: fmtDate(now) };
      case '6m':
        return { start: fmtDate(addMonths(now, -6)), end: fmtDate(now) };
      case '1y':
        return { start: fmtDate(addMonths(now, -12)), end: fmtDate(now) };
      case 'custom':
        return {
          start: chartCustomStart || fmtDate(addMonths(now, -12)),
          end: chartCustomEnd || fmtDate(now),
        };
      default: {
        const earliest = group?.snapshots?.[group.snapshots.length - 1];
        return {
          start: earliest ? fmtDate(new Date(parseUtc(earliest.timestamp))) : fmtDate(addMonths(now, -60)),
          end: fmtDate(now),
        };
      }
    }
  }

  async function loadChart(group) {
    if (!group) return;
    chartLoading = true;
    chartError = false;
    chartPoints = [];
    const { start, end } = rangeForPreset(group);
    try {
      const data = await analytics.cashByCurrencyHistory(start, end, 'month', group.entity_id, group.currency);
      chartPoints = (data || []).filter((d) => d.currency === group.currency);
    } catch {
      chartError = true;
      chartPoints = [];
    } finally {
      chartLoading = false;
    }
  }

  function setPreset(value) {
    chartPreset = value;
    if (chartGroup) loadChart(chartGroup);
  }

  function setCustom(which, value) {
    if (which === 'start') chartCustomStart = value;
    else chartCustomEnd = value;
    if (chartGroup) loadChart(chartGroup);
  }

  function chartLabels() {
    return chartPoints.map((p) => formatDate(`${p.date}-01`, { month: 'short', year: 'numeric' }));
  }

  function chartValues() {
    return chartPoints.map((p) => p.balance);
  }

  function selectEntity(id) {
    selectedEntity = id;
    currentPage = 1;
    expandedGroupId = null;
    chartPoints = [];
  }

  function toggleExpand(group) {
    if (expandedGroupId === group.key) {
      expandedGroupId = null;
      chartPoints = [];
      return;
    }
    expandedGroupId = group.key;
    chartPoints = [];
    chartError = false;
    loadChart(group);
  }

  async function loadAll() {
    loading = true;
    error = null;
    currentPage = 1;
    expandedGroupId = null;
    chartPoints = [];
    try {
      const [snapshotsData, entitiesData, balancesData] = await Promise.all([
        crud.balanceSnapshots.getList(),
        crud.entities.getList(),
        analytics.cashBalances(),
      ]);

      entityMap = {};
      for (const e of entitiesData || []) {
        entityMap[e.id] = e.name;
      }
      entities = entitiesData || [];
      balances = balancesData || [];
      snapshots = (snapshotsData || []).sort((a, b) => new Date(parseUtc(b.timestamp)) - new Date(parseUtc(a.timestamp)));
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'balances' });
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('balance-snapshots'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('balance-snapshots');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div>
    <div class="page-title-row">
      <h1 class="page-title">{t('balanceSnapshots.title')}</h1>
      <ReplayButton page="balance-snapshots" />
    </div>
    <p class="page-subtitle">{t('balanceSnapshots.subtitle')}</p>
  </div>
  <div class="page-actions">
    <Button variant="primary" size="sm" onclick={() => addModalOpen = true}>{t('balanceSnapshots.add')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('balanceSnapshots.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if groups.length === 0}
  <EmptyState title={t('balanceSnapshots.emptyTitle')} message={t('balanceSnapshots.emptyMsg')} />
{:else}
  <div class="filter-bar">
    <label>
      {t('balanceSnapshots.filterEntity')}
      <select bind:value={selectedEntity} onchange={() => selectEntity(selectedEntity)}>
        <option value={null}>{t('common.allEntities')}</option>
        {#each entities as entity}
          <option value={entity.id}>{entity.name}</option>
        {/each}
      </select>
    </label>
  </div>

  <div class="table-section">
    <div class="table-wrap">
      <table class="snapshot-table">
        <thead>
          <tr>
            <th>{t('common.entity')}</th>
            <th class="currency-col">{t('common.currency')}</th>
            <th class="num">{t('balanceSnapshots.current')}</th>
            <th class="num">{t('balanceSnapshots.lastSnapshot')}</th>
            <th>{t('balanceSnapshots.anchored')}</th>
            <th>{t('common.notes')}</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedGroups as group (group.key)}
            <tr class="group-row">
              <td class="cell-entity">
                <span class="cell-entity-inner">
                  <button
                    class="expand-btn"
                    aria-label={t('balanceSnapshots.toggleSnapshots')}
                    onclick={(e) => { e.stopPropagation(); toggleExpand(group); }}
                  >
                    <span class="expand-icon">{expandedGroupId === group.key ? '▼' : '▶'}</span>
                  </button>
                  {entityMap[group.entity_id] || group.entity_id}
                </span>
              </td>
              <td class="currency-col">{group.currency}</td>
              <td class="num">{fmt(group.current, group.currency)}</td>
              <td class="num">{group.last ? fmt(group.last.amount, group.currency) : '-'}</td>
              <td>
                {#if group.last}
                  <span class="anchor-cell">
                    <span>{formatDate(group.last.timestamp)}</span>
                    {#if ageVariant(ageDays(group))}
                      <Badge variant={ageVariant(ageDays(group))}>{t('balanceSnapshots.ageDays', { n: ageDays(group) })}</Badge>
                    {:else}
                      <span class="anchor-age">{t('balanceSnapshots.ageDays', { n: ageDays(group) })}</span>
                    {/if}
                  </span>
                {:else}
                  -
                {/if}
              </td>
              <td class="cell-notes">{group.last?.notes || '-'}</td>
            </tr>
            {#if expandedGroupId === group.key}
              <tr class="items-row">
                <td colspan="6">
                  <div class="expanded-body">
                    <div class="date-presets">
                      {#each PRESETS as preset}
                        <button
                          class="preset-btn"
                          class:active={chartPreset === preset.value}
                          onclick={() => setPreset(preset.value)}
                          disabled={chartLoading}
                        >{preset.label}</button>
                      {/each}
                      {#if chartPreset === 'custom'}
                        <TextInput type="date" placeholder={t('common.start')} value={chartCustomStart} oninput={(e) => setCustom('start', e.target.value)} />
                        <span class="custom-sep">—</span>
                        <TextInput type="date" placeholder={t('common.end')} value={chartCustomEnd} oninput={(e) => setCustom('end', e.target.value)} />
                      {/if}
                    </div>

                    <ChartCard title={t('balanceSnapshots.cashHistoryTitle', { entity: entityMap[group.entity_id] || group.entity_id, currency: group.currency })}>
                      {#if chartLoading}
                        <LoadingSpinner />
                      {:else if chartError}
                        <p class="chart-empty">{t('balanceSnapshots.chartError')}</p>
                        <div class="chart-retry">
                          <Button variant="secondary" size="sm" onclick={() => chartGroup && loadChart(chartGroup)}>{t('common.retry')}</Button>
                        </div>
                      {:else if chartPoints.length === 0}
                        <p class="chart-empty">{t('balanceSnapshots.noChartData')}</p>
                      {:else}
                        <LineChart
                          labels={chartLabels()}
                          datasets={[{ data: chartValues(), label: t('balanceSnapshots.current') }]}
                        />
                      {/if}
                    </ChartCard>

                    <div class="items-table-wrap">
                      {#if group.snapshots.length === 0}
                        <p class="chart-empty">{t('balanceSnapshots.noSnapshots')}</p>
                      {:else}
                        <table class="items-table">
                          <thead>
                            <tr>
                              <th>{t('common.date')}</th>
                              <th class="num">{t('common.amount')}</th>
                              <th>{t('common.notes')}</th>
                              <th class="actions-col">{t('common.actions')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {#each group.snapshots as snapshot (snapshot.id)}
                              <tr>
                                <td>{formatDateTime(snapshot.timestamp)}</td>
                                <td class="num">{fmt(snapshot.amount, group.currency)}</td>
                                <td class="cell-notes">{snapshot.notes || '-'}</td>
                                <td>
                                  <button class="icon-btn" title={t('balanceSnapshots.editAria')} aria-label={t('balanceSnapshots.editAria')} onclick={() => editSnapshot = snapshot}>
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                  </button>
                                  <button class="icon-btn icon-btn-danger" title={t('balanceSnapshots.deleteAria')} aria-label={t('balanceSnapshots.deleteAria')} onclick={() => deleteSnapshot = snapshot}>
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                                  </button>
                                </td>
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      {/if}
                    </div>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
    {#if totalPages > 1}
      <Pagination totalItems={groups.length} itemsPerPage={PER_PAGE} bind:currentPage={currentPage} />
    {/if}
  </div>
{/if}

<AddBalanceSnapshotModal open={addModalOpen} onclose={() => addModalOpen = false} onsuccess={loadAll} {snapshots} />
<EditBalanceSnapshotModal open={editSnapshot !== null} snapshot={editSnapshot} onclose={() => editSnapshot = null} onsuccess={loadAll} {snapshots} />
<ConfirmDeleteModal
  open={deleteSnapshot !== null}
  title={t('balanceSnapshots.deleteTitle')}
  message={deleteSnapshot ? t('balanceSnapshots.deleteMsg') : ''}
  onconfirm={async () => {
    if (!deleteSnapshot) return;
    await api.del(`/balance-snapshots/${deleteSnapshot.id}`);
    deleteSnapshot = null;
    loadAll();
  }}
  oncancel={() => deleteSnapshot = null}
/>

<TutorialOverlay definition={balanceSnapshotsTutorial} page="balance-snapshots" onfinish={loadAll} />

<style>
  .page-header {
    display: flex;
    align-items: flex-start;
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

  .page-subtitle {
    margin: var(--space-1) 0 0;
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .page-actions {
    display: flex;
    gap: var(--space-3);
  }

  .filter-bar {
    margin-bottom: var(--space-4);
  }

  .filter-bar label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .filter-bar select {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
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

  .snapshot-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .snapshot-table th {
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

  .snapshot-table th.num {
    text-align: right;
  }

  .snapshot-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .currency-col {
    width: 70px;
  }

  .group-row {
    cursor: default;
  }

  .group-row:hover {
    background: var(--color-surface-hover);
  }

  .cell-entity { font-weight: var(--font-weight-semibold); }
  .cell-entity-inner { display: inline-flex; align-items: center; gap: var(--space-2); }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
    padding: 0;
    display: inline-flex;
    align-items: center;
  }

  .expand-icon {
    font-size: 10px;
    color: var(--color-text-muted);
    width: 12px;
    text-align: center;
  }

  .anchor-cell {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .anchor-age {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .items-row td {
    padding: 0 !important;
    border-bottom: 1px solid var(--color-border);
  }

  .expanded-body {
    padding: var(--space-4);
    background: var(--color-surface-alt);
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

  .chart-empty {
    margin: 0;
    padding: var(--space-6);
    text-align: center;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  .chart-retry {
    display: flex;
    justify-content: center;
    padding-bottom: var(--space-4);
  }

  .items-table-wrap {
    padding-top: var(--space-4);
  }

  .items-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-xs);
  }

  .items-table th,
  .items-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .items-table th {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
  }

  .items-table th.num,
  .items-table td.num {
    text-align: right;
  }

  .items-table th.actions-col,
  .items-table td:last-child {
    text-align: right;
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .cell-notes {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
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
