<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { api } from '$lib/api/client.js';
  import { displayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { formatAmount, formatDate, formatPercent, maskAmount } from '$lib/utils/format.svelte';
  import { BUCKET_COLORS, STRATEGY_BUCKETS, driftText } from '$lib/utils/strategy.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import Card from '$lib/components/Card.svelte';
  import LineChart from '$lib/components/charts/LineChart.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import StrategySetModal from '$lib/components/modals/StrategySetModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { strategy as strategyTutorial } from '$lib/tutorial/definitions/index';
  import strategyMock from '$lib/tutorial/mocks/strategy';

  tutorialStore.registerMock('strategy', strategyMock);

  let loading = $state(true);
  let error = $state(null);
  let sets = $state([]);
  let drift = $state(null);

  let history = $state({ points: [] });
  let historyLoading = $state(true);
  let historyError = $state(null);
  let historyPreset = $state('1y');

  let historyPresets = $derived([
    { value: '3m', label: t('common.presetShort3m') },
    { value: '6m', label: t('common.presetShort6m') },
    { value: '1y', label: t('common.presetShort1y') },
    { value: 'all', label: t('common.presetAll') },
  ]);

  let modalOpen = $state(false);
  let editing = $state(null);
  let deleteOpen = $state(false);
  let deleting = $state(null);

  let currencyCode = $derived(displayCurrency());
  let symbol = $derived(currencySymbol());
  let asOf = $derived(drift?.as_of ?? '');
  let currentDate = $derived(drift?.effective_from ?? '');

  async function load() {
    loading = true;
    error = null;
    try {
      const [setsData, driftData] = await Promise.all([
        api.get('/strategy'),
        api.get(`/strategy/drift?display_currency=${encodeURIComponent(displayCurrency())}`),
      ]);
      sets = setsData ?? [];
      drift = driftData;
    } catch (e) {
      error = e.message || t('strategy.loadFailed');
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
    loadHistory();
  });

  function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  function addMonths(date, months) {
    const copy = new Date(date);
    copy.setMonth(copy.getMonth() + months);
    return copy;
  }

  function historyRange() {
    const now = new Date();
    if (historyPreset === '3m') {
      return { start: isoDate(addMonths(now, -3)), end: isoDate(now), interval: 'week' };
    }
    if (historyPreset === '6m') {
      return { start: isoDate(addMonths(now, -6)), end: isoDate(now), interval: 'week' };
    }
    if (historyPreset === '1y') {
      return { start: isoDate(addMonths(now, -12)), end: isoDate(now), interval: 'month' };
    }
    return { start: '2020-01-01', end: isoDate(now), interval: 'month' };
  }

  async function loadHistory() {
    historyLoading = true;
    historyError = null;
    try {
      const range = historyRange();
      history = (await api.get(
        `/strategy/history?start_date=${range.start}&end_date=${range.end}&interval=${range.interval}&display_currency=${encodeURIComponent(displayCurrency())}`,
      )) ?? { points: [] };
    } catch (e) {
      historyError = e.message || t('strategy.loadFailed');
    } finally {
      historyLoading = false;
    }
  }

  let historyDates = $derived.by(() => [...new Set((history?.points ?? []).map((p) => p.date))].sort());

  let historySeries = $derived.by(() =>
    STRATEGY_BUCKETS.map((bucket) => {
      const byDate = new Map(
        (history?.points ?? []).filter((p) => p.bucket === bucket).map((p) => [p.date, p]),
      );
      return {
        bucket,
        actual: historyDates.map((date) => byDate.get(date)?.share_pct ?? null),
        target: historyDates.map((date) => byDate.get(date)?.target_pct ?? null),
      };
    }),
  );

  let latestUnassigned = $derived.by(() => {
    const unassigned = (history?.points ?? []).filter((p) => p.bucket === 'unassigned');
    return unassigned[unassigned.length - 1]?.share_pct ?? 0;
  });

  function setStatus(item) {
    if (!asOf) return '';
    if (item.effective_from > asOf) return 'planned';
    if (item.effective_from === currentDate) return 'current';
    return 'past';
  }

  function statusLabel(status) {
    if (status === 'current') return t('strategy.statusCurrent');
    if (status === 'planned') return t('strategy.statusPlanned');
    return t('strategy.statusPast');
  }

  function chips(item) {
    return STRATEGY_BUCKETS.filter((bucket) => (item.targets?.[bucket] ?? 0) > 0).map((bucket) => ({
      bucket,
      value: item.targets[bucket],
    }));
  }

  function money(value) {
    return maskAmount(`${symbol}${formatAmount(value)}`, symbol);
  }

  function openAdd() {
    editing = null;
    modalOpen = true;
  }

  function openEdit(item) {
    editing = item;
    modalOpen = true;
  }

  function confirmDelete(item) {
    deleting = item;
    deleteOpen = true;
  }

  async function deleteSet() {
    await api.del(`/strategy/${encodeURIComponent(deleting.effective_from)}`);
    deleteOpen = false;
    deleting = null;
    await load();
  }

  let driftRows = $derived.by(() => {
    if (!drift?.buckets?.length) return [];
    const rows = [...drift.buckets].sort(
      (a, b) => b.target_pct - a.target_pct || a.bucket.localeCompare(b.bucket),
    );
    if (drift.unassigned && drift.unassigned.value !== 0) {
      rows.push({
        bucket: 'unassigned',
        unassigned: true,
        target_pct: null,
        value: drift.unassigned.value,
        share_pct: drift.unassigned.share_pct,
        drift_pp: null,
        amount_to_move: null,
        rate_missing: drift.unassigned.rate_missing,
      });
    }
    return rows;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('strategy.title')}</h1>
    <ReplayButton page="strategy" />
  </div>
  <div class="page-actions">
    <span class="strategy-add">
      <Button variant="primary" size="sm" onclick={openAdd}>{t('strategy.add')}</Button>
    </span>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('strategy.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={load}>{t('common.retry')}</Button>
  </div>
{:else if sets.length === 0}
  <EmptyState title={t('strategy.emptyTitle')} message={t('strategy.emptyMsg')} />
{:else}
  <Card class="strategy-policy">
    <h2 class="section-title">{t('strategy.setsTitle')}</h2>
    <div class="set-list">
      {#each sets as item (item.effective_from)}
        <div class="set-row">
          <span class="set-date">{formatDate(item.effective_from)}</span>
          <span class="badge badge-{setStatus(item)}">{statusLabel(setStatus(item))}</span>
          <span class="chips">
            {#each chips(item) as chip (chip.bucket)}
              <span class="chip">{t(`bucket.${chip.bucket}`)} {formatPercent(chip.value)}</span>
            {/each}
          </span>
          <span class="set-actions">
            <button class="link-btn" onclick={() => openEdit(item)}>{t('strategy.edit')}</button>
            <button class="link-btn danger" onclick={() => confirmDelete(item)}>{t('strategy.delete')}</button>
          </span>
        </div>
      {/each}
    </div>
  </Card>

  <Card class="strategy-drift">
    {#if drift?.effective_from}
      <h2 class="section-title">
        {t('strategy.driftTitle')} · {t('strategy.driftTarget', { date: formatDate(drift.effective_from) })}
      </h2>
      <p class="values-in">{t('strategy.valuesIn', { currency: currencyCode })}</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>{t('strategy.colBucket')}</th>
              <th class="num">{t('strategy.colTarget')}</th>
              <th class="num">{t('strategy.colActual')}</th>
              <th class="num">{t('strategy.colDrift')}</th>
              <th class="num">{t('strategy.colAmount')}</th>
            </tr>
          </thead>
          <tbody>
            {#each driftRows as row (row.bucket)}
              <tr class:band={row.drift_pp !== null && Math.abs(row.drift_pp) > 5} class:muted={row.unassigned}>
                <td>
                  {row.unassigned ? t('strategy.unassigned') : t(`bucket.${row.bucket}`)}
                  {#if row.rate_missing && !privacyHidden()}<span class="flag">*</span>{/if}
                </td>
                <td class="num">{row.target_pct !== null ? formatPercent(row.target_pct) : '—'}</td>
                <td class="num">{formatPercent(row.share_pct)}</td>
                <td class="num">{driftText(row.drift_pp)}</td>
                <td class="num">{row.amount_to_move !== null ? money(row.amount_to_move) : '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="note strategy-band">{t('strategy.band')}</p>
      {#if drift.rate_missing}
        <p class="note">* {t('strategy.rateMissing')}</p>
      {/if}
    {:else}
      <h2 class="section-title">{t('strategy.driftTitle')}</h2>
      <p class="note strong">{t('strategy.noTarget')}</p>
      {#if sets.length > 0}
        <p class="note">{t('strategy.noTargetMsg', { date: formatDate(sets[0].effective_from) })}</p>
      {:else}
        <p class="note">{t('strategy.noTargetNoFuture')}</p>
      {/if}
    {/if}
  </Card>

  <Card class="strategy-history">
    <div class="history-head">
      <h2 class="section-title">{t('strategy.historyTitle')}</h2>
      <div class="date-presets">
        {#each historyPresets as preset (preset.value)}
          <button
            class="preset-btn"
            class:active={historyPreset === preset.value}
            onclick={() => { historyPreset = preset.value; loadHistory(); }}
            disabled={historyLoading}
          >{preset.label}</button>
        {/each}
      </div>
    </div>
    {#if historyLoading}
      <LoadingSpinner />
    {:else if historyError}
      <p class="note strong">{historyError}</p>
    {:else if historyDates.length === 0}
      <p class="note">{t('strategy.historyEmpty')}</p>
    {:else}
      <p class="history-legend">{t('strategy.historyLegend')}</p>
      <div class="history-grid">
        {#each historySeries as series (series.bucket)}
          <div class="history-card">
            <h3 class="history-bucket">{t(`bucket.${series.bucket}`)}</h3>
            <LineChart
              labels={historyDates}
              datasets={[
                { label: t('strategy.historyActual'), data: series.actual, color: BUCKET_COLORS[series.bucket] },
                { label: t('strategy.historyTarget'), data: series.target, color: BUCKET_COLORS[series.bucket], dashed: true, stepped: true },
              ]}
              unit="percent"
              maskable={false}
              showLegend={false}
              height={150}
            />
          </div>
        {/each}
      </div>
      {#if latestUnassigned > 0}
        <p class="note">{t('strategy.unassignedNote', { share: formatPercent(latestUnassigned) })}</p>
      {/if}
      <p class="note">{t('strategy.historyCaveat')}</p>
    {/if}
  </Card>
{/if}

<StrategySetModal
  open={modalOpen}
  onclose={() => (modalOpen = false)}
  target={editing}
  defaultDate={asOf}
  onsaved={load}
/>

<ConfirmDeleteModal
  open={deleteOpen}
  onclose={() => (deleteOpen = false)}
  onconfirm={deleteSet}
  title={t('strategy.deleteTitle')}
  message={t('strategy.deleteNote')}
  entityName={deleting ? formatDate(deleting.effective_from) : ''}
/>

<TutorialOverlay definition={strategyTutorial} page="strategy" onfinish={load} />

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
    align-items: center;
    gap: var(--space-3);
  }

  .strategy-policy {
    margin-bottom: var(--space-5);
  }

  .strategy-drift {
    margin-bottom: var(--space-5);
  }

  .history-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }

  .history-head .section-title {
    margin: 0;
  }

  .date-presets {
    display: flex;
    align-items: center;
    gap: var(--space-2);
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

  .preset-btn.active {
    border-color: var(--color-primary);
    background: var(--color-primary-bg);
    color: var(--color-primary);
  }

  .preset-btn:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .history-legend {
    margin: 0 0 var(--space-3);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .history-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

  .history-card {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3);
  }

  .history-bucket {
    margin: 0 0 var(--space-2);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
  }

  .section-title {
    font-size: var(--font-size-base);
    margin: 0 0 var(--space-3);
  }

  .set-list {
    display: flex;
    flex-direction: column;
  }

  .set-row {
    display: grid;
    grid-template-columns: 110px 90px 1fr auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--color-border);
    font-size: var(--font-size-sm);
  }

  .set-row:last-child {
    border-bottom: none;
  }

  .set-date {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-primary);
  }

  .badge {
    justify-self: start;
    padding: 1px var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    text-align: center;
  }

  .badge-current {
    background: var(--color-success-bg);
    color: var(--color-success);
  }

  .badge-planned {
    background: var(--color-info-bg);
    color: var(--color-info);
  }

  .badge-past {
    background: var(--color-surface-alt);
    color: var(--color-text-muted);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .chip {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .set-actions {
    display: flex;
    gap: var(--space-3);
  }

  .link-btn {
    background: none;
    border: none;
    padding: 0;
    font-family: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-primary);
    cursor: pointer;
  }

  .link-btn:hover {
    text-decoration: underline;
  }

  .link-btn.danger {
    color: var(--color-danger);
  }

  .values-in {
    margin: 0 0 var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .table-wrap {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .data-table th {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
  }

  .data-table th.num,
  .data-table td.num {
    text-align: right;
  }

  .data-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .data-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .band td.num {
    font-weight: var(--font-weight-semibold);
  }

  .band td {
    background: var(--color-warning-bg);
  }

  .muted td {
    color: var(--color-text-muted);
  }

  .flag {
    margin-left: 2px;
    color: var(--color-warning);
  }

  .note {
    margin: var(--space-2) 0 0;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .note.strong {
    color: var(--color-text-primary);
    font-size: var(--font-size-sm);
  }

  .error-card {
    background: var(--color-danger-bg);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .error-message {
    margin: 0;
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }

  @media (max-width: 768px) {
    .history-grid {
      grid-template-columns: 1fr;
    }

    .set-row {
      grid-template-columns: 1fr auto;
    }

    .chips {
      grid-column: 1 / -1;
    }
  }
</style>
