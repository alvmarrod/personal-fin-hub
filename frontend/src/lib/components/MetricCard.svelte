<script>
  import InfoTip from './InfoTip.svelte';

  let { label, value = null, change = null, changeLabel = '', variant = 'neutral', valueVariant = null, currencySymbol = '', currencyCode = '', tooltip = null } = $props();

  function fmt(val) {
    if (val == null) return '—';
    if (typeof val === 'string') return val;
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 10_000_000) return `${sign}${currencySymbol}${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 10_000) return `${sign}${currencySymbol}${(abs / 1_000).toFixed(1)}k`;
    const decimals = currencyCode === 'JPY' ? 0 : 2;
    return `${sign}${currencySymbol}${abs.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
  }

  function full() {
    if (value == null) return '';
    if (typeof value === 'string') return value;
    const sign = value < 0 ? '-' : '';
    const abs = Math.abs(value);
    const decimals = currencyCode === 'JPY' ? 0 : 2;
    return `${sign}${currencySymbol}${abs.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
  }
</script>

<div class="metric-card" title={full() || undefined}>
  <div class="metric-label">
    <span class="metric-label-text">{label}</span>
    {#if tooltip}
      <InfoTip text={tooltip} label={label} />
    {/if}
  </div>
  <div class="metric-value" class:metric-value-positive={valueVariant === 'positive'} class:metric-value-negative={valueVariant === 'negative'}>{#if valueVariant}<span class="change-arrow">{valueVariant === 'positive' ? '▲' : '▼'}</span>{/if}{fmt(value)}</div>
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
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin-bottom: var(--space-1);
  }

  .metric-label-text {
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

  .metric-value-positive {
    color: var(--color-success);
  }

  .metric-value-negative {
    color: var(--color-danger);
  }

  .metric-value .change-arrow {
    font-size: 0.6em;
    margin-right: 4px;
  }

  .metric-change {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .metric-change-positive {
    color: var(--color-success);
  }

  .metric-change-negative {
    color: var(--color-danger);
  }

  .metric-change-neutral {
    color: var(--color-text-muted);
  }

  .change-arrow {
    font-size: 10px;
    margin-right: 2px;
  }
</style>
