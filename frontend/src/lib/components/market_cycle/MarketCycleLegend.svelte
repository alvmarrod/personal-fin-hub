<script>
  import { t } from '$lib/i18n/index.svelte';
</script>

<ul class="legend">
  <li class="legend-item">
    <span class="swatch swatch-active"></span>
    <span>{t('marketCycle.legend.activeState')}</span>
  </li>
  <li class="legend-item">
    <span class="swatch swatch-inactive"></span>
    <span>{t('marketCycle.legend.inactiveState')}</span>
  </li>
  <li class="legend-item">
    <span class="swatch swatch-emerging"></span>
    <span>{t('marketCycle.legend.emergingTransition')}</span>
  </li>
  <li class="legend-item">
    <span class="swatch swatch-approaching"></span>
    <span>{t('marketCycle.legend.approachingTransition')}</span>
  </li>
  <li class="legend-item">
    <span class="swatch swatch-entry"></span>
    <span>{t('marketCycle.legend.entryCondition')}</span>
  </li>
  <li class="legend-item">
    <span class="swatch swatch-strong"></span>
    <span>{t('marketCycle.legend.strongEntrySignal')}</span>
  </li>
</ul>

<style>
  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .swatch {
    width: 14px;
    height: 14px;
    border-radius: var(--radius-full);
    flex-shrink: 0;
    border: 2px solid var(--color-border);
  }

  .swatch-active {
    background: var(--color-success);
    border-color: var(--color-success);
  }

  .swatch-inactive {
    background: var(--color-surface);
  }

  .swatch-emerging {
    background: var(--color-warning-bg);
    border-color: var(--color-warning);
  }

  .swatch-approaching {
    background: var(--color-warning);
    border-color: var(--color-warning);
  }

  .swatch-entry {
    background: var(--color-success-bg);
    border-color: var(--color-success);
  }

  .swatch-strong {
    background: var(--color-success);
    border-color: var(--color-success);
  }
</style>
