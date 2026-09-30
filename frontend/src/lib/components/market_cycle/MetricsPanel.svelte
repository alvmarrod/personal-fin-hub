<script>
  import { t } from '$lib/i18n/index.svelte';
  import { metricLabel, formatValue } from '$lib/marketCycle/signals.js';

  let { metrics = [] } = $props();

  function valueText(metric) {
    return metric.kind === 'direction' ? formatValue(metric.value, null, t) : formatValue(metric.value, '%', t);
  }

  function deltaText(metric) {
    if (metric.kind !== 'level' || typeof metric.delta !== 'number') return '';
    return `${metric.delta > 0 ? '+' : ''}${metric.delta.toFixed(2)}`;
  }
</script>

<section class="metrics-panel">
  <h2 class="panel-title">{t('marketCycle.metricsTitle')}</h2>
  <table class="metrics-table">
    <thead>
      <tr>
        <th scope="col">{t('marketCycle.metricColumn')}</th>
        <th scope="col" class="num">{t('marketCycle.valueColumn')}</th>
      </tr>
    </thead>
    <tbody>
      {#each metrics as metric (metric.kpi)}
        <tr>
          <td>{metricLabel(metric.kpi, t)}</td>
          <td class="num">
            <span class="metric-value">{valueText(metric)}</span>
            {#if deltaText(metric)}
              <span class="metric-delta">{deltaText(metric)}</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .metrics-panel {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .panel-title {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-bold);
    margin: 0 0 var(--space-3);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .metrics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .metrics-table th,
  .metrics-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .metrics-table th {
    font-weight: var(--font-weight-medium);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .metrics-table tbody tr:last-child td {
    border-bottom: none;
  }

  .metrics-table .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .metric-delta {
    margin-left: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
</style>
