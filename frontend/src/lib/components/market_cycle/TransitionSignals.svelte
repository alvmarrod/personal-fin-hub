<script>
  import { t } from '$lib/i18n/index.svelte';
  import { NAME_TO_ID, stateNameKey } from '$lib/marketCycle/states.js';
  import { describeSignal, describePart } from '$lib/marketCycle/signals.js';

  let { transitions = [], approachingKey = null } = $props();

  function stateLabel(name) {
    const id = NAME_TO_ID[name];
    return id ? t(stateNameKey(id)) : name;
  }

  function keyOf(transition) {
    return `${transition.source}->${transition.target}`;
  }
</script>

<section class="signals-panel">
  <h2 class="panel-title">{t('marketCycle.signalsTitle')}</h2>
  <ul class="transition-list">
    {#each transitions as tr (keyOf(tr))}
      {@const isApproaching = keyOf(tr) === approachingKey}
      <li class="transition" class:approaching={isApproaching}>
        {#if isApproaching}
          <div class="transition-head">
            <span class="transition-title">{stateLabel(tr.source)} → {stateLabel(tr.target)}</span>
            <span class="status" class:status-on={tr.status !== 'Inactive'}>
              {t(`marketCycle.status.${tr.status.toLowerCase()}`)}
            </span>
          </div>
          {@render body(tr)}
        {:else}
          <details>
            <summary>
              <span class="transition-title">{stateLabel(tr.source)} → {stateLabel(tr.target)}</span>
              <span class="status" class:status-on={tr.status !== 'Inactive'}>
                {t(`marketCycle.status.${tr.status.toLowerCase()}`)}
              </span>
            </summary>
            {@render body(tr)}
          </details>
        {/if}
      </li>
    {/each}
  </ul>
</section>

{#snippet body(transition)}
  <ul class="signal-list">
    {#each transition.signals ?? [] as signal (signal.code)}
      <li class="signal" class:met={signal.met}>
        <span class="signal-verdict">{signal.met ? t('marketCycle.met') : t('marketCycle.notMet')}</span>
        {#if signal.kind === 'combination'}
          <div class="combination">
            {#each signal.parts ?? [] as part, i (i)}
              <div class="part" class:met={part.met}>{describePart(part, t)}</div>
            {/each}
          </div>
        {:else}
          <span class="signal-desc">{describeSignal(signal, t)}</span>
        {/if}
      </li>
    {/each}
  </ul>
  <div class="progress">
    {t('marketCycle.held', {
      held: transition.held_months ?? 0,
      required: transition.required_months ?? 0,
    })}
  </div>
{/snippet}

<style>
  .signals-panel {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: var(--space-5);
  }

  .panel-title {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-bold);
    margin: 0 0 var(--space-3);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .transition-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .transition {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
  }

  .transition.approaching {
    border-color: var(--color-warning);
    background: var(--color-warning-bg);
  }

  .transition-head,
  summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    cursor: default;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
  }

  summary {
    cursor: pointer;
  }

  .status {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    text-transform: lowercase;
  }

  .status-on {
    color: var(--color-warning);
    font-weight: var(--font-weight-medium);
  }

  .signal-list {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .signal {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
  }

  .signal-verdict {
    flex: 0 0 auto;
    font-size: var(--font-size-xs);
    padding: 0 var(--space-2);
    border-radius: var(--radius-full);
    background: var(--color-surface-alt, var(--color-surface));
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .signal.met .signal-verdict {
    border-color: var(--color-success);
    color: var(--color-success);
  }

  .signal-desc {
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .combination {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .part {
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .progress {
    margin-top: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
</style>
