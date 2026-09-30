<script>
  import { onMount } from 'svelte';
  import { analytics, MARKET_CYCLE_SCOPES } from '$lib/api/analytics.js';
  import { t } from '$lib/i18n/index.svelte';
  import { formatDate, formatDateTime } from '$lib/utils/format.svelte';
  import { LoadingSpinner, EmptyState, Badge, Select, Button } from '$lib/components/index.js';
  import StateDiagram from '$lib/components/market_cycle/StateDiagram.svelte';
  import MarketCycleLegend from '$lib/components/market_cycle/MarketCycleLegend.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { marketCycle as marketCycleTutorial } from '$lib/tutorial/definitions/index';
  import marketCycleMock from '$lib/tutorial/mocks/market-cycle';
  import { NAME_TO_ID, stateNameKey } from '$lib/marketCycle/states.js';

  tutorialStore.registerMock('investment-market-cycle', marketCycleMock);

  // Spain/Eurozone is the only scope with sourced data today; the others are
  // shown but disabled until their sources are wired.
  const DEFAULT_SCOPE = 'spain-eurozone';

  let loading = $state(true);
  let error = $state(null);
  let missing = $state(false);
  let status = $state(null);
  let scope = $state(DEFAULT_SCOPE);

  const scopeOptions = MARKET_CYCLE_SCOPES.map((s) => ({
    value: s.key,
    label: s.ready ? t(s.labelKey) : `${t(s.labelKey)} (${t('marketCycle.scope.notReady')})`,
    disabled: !s.ready,
  }));

  const ENTRY_VARIANT = { strong: 'success', favourable: 'success', none: 'default' };
  const STATUS_RANK = { Triggered: 3, Near: 2, Emerging: 1, Inactive: 0 };

  let currentState = $derived(status?.current_state ?? null);
  let transitions = $derived(status?.active_transitions ?? []);
  let entrySignals = $derived(status?.entry_signals ?? 'none');
  let approaching = $derived(
    [...transitions]
      .filter((tr) => STATUS_RANK[tr.status] > 0)
      .sort((a, b) => STATUS_RANK[b.status] - STATUS_RANK[a.status] || a.priority - b.priority)[0] ?? null,
  );

  function stateLabel(idOrName) {
    const id = typeof idOrName === 'number' ? idOrName : NAME_TO_ID[idOrName];
    return id ? t(stateNameKey(id)) : String(idOrName ?? '');
  }

  async function load() {
    loading = true;
    error = null;
    missing = false;
    try {
      status = await analytics.investmentMarketCycle(scope);
    } catch (e) {
      if (e.status === 400) {
        missing = true;
        status = null;
      } else {
        error = e.message || t('marketCycle.loadError');
      }
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('marketCycle.title')}</h1>
    <ReplayButton page="investment-market-cycle" />
  </div>
  <div class="page-actions">
    {#if status}
      <span class="last-update">{t('marketCycle.lastUpdate')}: {formatDateTime(status.last_update)}</span>
    {/if}
    <Select
      value={scope}
      options={scopeOptions}
      onchange={(e) => {
        scope = e.target.value;
        load();
      }}
    />
    <Button variant="secondary" size="sm" onclick={load}>{t('marketCycle.refresh')}</Button>
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('marketCycle.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={load}>{t('common.retry')}</Button>
  </div>
{:else if missing}
  <div class="warning-banner">
    <div class="warning-icon">⚠</div>
    <div class="warning-content">
      <strong>{t('marketCycle.missingTitle')}</strong>
      <p>{t('marketCycle.missingMsg')}</p>
    </div>
  </div>
  <EmptyState title={t('marketCycle.emptyTitle')} message={t('marketCycle.emptyMsg')} />
{:else if status}
  <div class="cycle-main">
    <div class="legend-col">
      <MarketCycleLegend />
    </div>
    <div class="diagram-col">
      <StateDiagram currentStateId={currentState?.id} {transitions} />
      {#if status.ambiguous_confirmation}
        <div class="ambiguous-chip">
          <Badge variant="warning">{t('marketCycle.ambiguous')}</Badge>
        </div>
      {/if}
    </div>
  </div>

  <div class="supporting-panel">
    <div class="panel-row">
      <Badge variant={ENTRY_VARIANT[entrySignals]}>
        {t(`marketCycle.entry.${entrySignals}`)}{entrySignals === 'strong' ? ' ★' : ''}
      </Badge>
      <span class="panel-current">
        {t('marketCycle.currentState')}: <strong>{stateLabel(currentState?.id)}</strong>
        ({t('marketCycle.since')} {formatDate(status.current_state_since)})
      </span>
    </div>
    <div class="panel-row">
      <span class="panel-approaching">
        {#if approaching}
          {t('marketCycle.approaching')}: {stateLabel(approaching.source)} → {stateLabel(approaching.target)}
          ({t(`marketCycle.status.${approaching.status.toLowerCase()}`)})
        {:else}
          {t('marketCycle.noTransition')}
        {/if}
      </span>
    </div>
  </div>
{/if}

<TutorialOverlay definition={marketCycleTutorial} page="investment-market-cycle" onfinish={load} />

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
    gap: var(--space-3);
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

  .last-update {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .cycle-main {
    display: flex;
    gap: var(--space-6);
    align-items: flex-start;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
  }

  .legend-col {
    flex: 0 0 auto;
    min-width: 180px;
  }

  .diagram-col {
    flex: 1 1 auto;
    position: relative;
    min-width: 0;
  }

  .ambiguous-chip {
    position: absolute;
    top: 0;
    right: 0;
  }

  .supporting-panel {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .panel-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .panel-current,
  .panel-approaching {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .warning-banner {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    background: var(--color-warning-bg);
    border: 1px solid var(--color-warning);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .warning-icon {
    font-size: var(--font-size-xl);
    color: var(--color-warning);
    flex-shrink: 0;
  }

  .warning-content strong {
    display: block;
    margin-bottom: var(--space-1);
    color: var(--color-warning);
  }

  .warning-content p {
    margin: 0;
    font-size: var(--font-size-sm);
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
