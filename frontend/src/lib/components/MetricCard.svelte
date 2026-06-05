<script>
  let { label, value, change = null, changeLabel = '', variant = 'neutral' } = $props();
</script>

<div class="metric-card">
  <div class="metric-label">{label}</div>
  <div class="metric-value">{value}</div>
  {#if change !== null}
    <div class="metric-change metric-change-{variant}">
      {#if variant === 'positive'}<span class="change-arrow">&#9650;</span>
      {:else if variant === 'negative'}<span class="change-arrow">&#9660;</span>
      {/if}
      {change}% {changeLabel}
    </div>
  {/if}
</div>

<style>
  .metric-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    box-shadow: var(--shadow-sm);
  }

  .metric-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin-bottom: var(--space-1);
  }

  .metric-value {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    margin-bottom: var(--space-2);
  }

  .metric-change {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .metric-change-positive {
    color: var(--color-success);
  }

  .metric-change-negative {
    color: var(--color-error);
  }

  .metric-change-neutral {
    color: var(--color-text-muted);
  }

  .change-arrow {
    font-size: 10px;
    margin-right: 2px;
  }
</style>
