<script>
  let { label, value = 0, change = null, changeLabel = '', variant = 'neutral', currencySymbol = '', currencyCode = '' } = $props();

  function fmt(val) {
    if (val == null) return '—';
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 10_000_000) return `${sign}${currencySymbol}${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 10_000) return `${sign}${currencySymbol}${(abs / 1_000).toFixed(1)}k`;
    const decimals = currencyCode === 'JPY' ? 0 : 2;
    return `${sign}${currencySymbol}${abs.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
  }

  function full() {
    if (value == null) return '';
    const sign = value < 0 ? '-' : '';
    const abs = Math.abs(value);
    return `${sign}${currencySymbol}${abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
</script>

<div class="metric-card" title={full() || undefined}>
  <div class="metric-label">{label}</div>
  <div class="metric-value">{fmt(value)}</div>
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
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .metric-value {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-primary);
    margin-bottom: var(--space-2);
    white-space: nowrap;
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
