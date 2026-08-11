<script>
  import { t } from '$lib/i18n/index.svelte';
  import { formatTimestamp } from '$lib/preferences/timezone.svelte';
  import { marketApi, marketDataLastUpdated, dismissOutage } from '$lib/stores/health.svelte';

  let _marketApi = $derived(marketApi());
  let _dataDate = $derived(marketDataLastUpdated());
  let _freshnessLabel = $derived(
    _dataDate
      ? t('health.marketDataTitle', { date: formatTimestamp(_dataDate) })
      : t('health.marketDataNone'),
  );

  function handleDismiss() {
    dismissOutage();
  }
</script>

<div class="health-badges">
  <div class="badge freshness-badge" title={_freshnessLabel}>
    <span class="badge-dot freshness-dot"></span>
    <span class="badge-text">{_freshnessLabel}</span>
  </div>

  {#if _marketApi === 'unavailable'}
    <div class="badge outage-badge">
      <span class="badge-dot outage-dot"></span>
      <span class="badge-text">{t('health.marketApiUnavailable')}</span>
      <button class="badge-dismiss" onclick={handleDismiss} title={t('health.dismiss')}>×</button>
    </div>
  {/if}
</div>

<style>
  .health-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-6);
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-full);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .freshness-badge {
    background: var(--color-surface-alt);
    color: var(--color-text-secondary);
  }

  .outage-badge {
    background: var(--color-warning-light, rgba(240, 140, 0, 0.1));
    color: var(--color-warning, #856404);
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .freshness-dot {
    background: var(--color-text-muted);
  }

  .outage-dot {
    background: var(--color-warning, #f08c00);
  }

  .badge-text {
    white-space: nowrap;
  }

  .badge-dismiss {
    background: none;
    border: none;
    padding: 0;
    margin-left: var(--space-1);
    font-size: var(--font-size-sm);
    line-height: 1;
    cursor: pointer;
    color: inherit;
    opacity: 0.6;
    transition: opacity var(--transition-fast);
  }

  .badge-dismiss:hover {
    opacity: 1;
  }
</style>
