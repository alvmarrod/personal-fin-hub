<script>
  import { t } from '$lib/i18n/index.svelte';
  import { goto } from '$app/navigation';
  import BubbleDeviationChart from './charts/BubbleDeviationChart.svelte';
  import Button from './Button.svelte';
  import { bubblePoints, hiddenOnTarget } from '$lib/utils/strategy.js';

  let { drift = null } = $props();

  let points = $derived(bubblePoints(drift?.buckets ?? []));
  let hidden = $derived(hiddenOnTarget(drift?.buckets ?? []));
</script>

{#if drift?.effective_from}
  <BubbleDeviationChart {points} height={300} />
  {#if hidden > 0}
    <p class="card-note">{t('dashboard.onTargetAtZero', { count: hidden })}</p>
  {/if}
{:else}
  <div class="strategy-cta">
    <Button variant="primary" size="sm" onclick={() => goto('/strategy')}>
      {t('dashboard.goToStrategy')}
    </Button>
  </div>
{/if}

<style>
  .card-note {
    margin: var(--space-2) 0 0;
    text-align: center;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .strategy-cta {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 300px;
  }
</style>
