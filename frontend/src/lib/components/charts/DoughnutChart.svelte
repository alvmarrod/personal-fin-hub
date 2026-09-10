<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { segmentLabelsPlugin } from './segmentLabelsPlugin.js';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { MASK } from '$lib/utils/format.svelte';

  Chart.register(...registerables);

  let { labels = [], data = [], colors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'], currencySymbol = '' } = $props();

  let canvas;
  let chart;

  function buildChartConfig() {
    return {
      type: 'doughnut',
      data: {
        labels: [...labels],
        datasets: [{
          data: [...data],
          backgroundColor: [...colors],
          borderWidth: 2,
          borderColor: '#ffffff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '60%',
        _currencySymbol: currencySymbol,
        _privacyHidden: privacyHidden(),
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (privacyHidden()) return ` ${ctx.label}: ${MASK}${currencySymbol}`;
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = ((ctx.parsed / total) * 100).toFixed(1);
                return ` ${ctx.label}: ${currencySymbol}${ctx.parsed.toLocaleString()} (${pct}%)`;
              },
            },
          },
        },
      },
      plugins: [segmentLabelsPlugin],
    };
  }

  onMount(() => {
    const ctx = canvas.getContext('2d');
    chart = new Chart(ctx, buildChartConfig());
  });

  onDestroy(() => {
    chart?.destroy();
    chart = null;
  });

  $effect(() => {
    if (chart?.canvas && canvas?.isConnected) {
      const config = buildChartConfig();
      chart.data.labels = [...labels];
      chart.data.datasets[0].data = [...data];
      chart.data.datasets[0].backgroundColor = [...colors];
      chart.options.plugins.tooltip = config.options.plugins.tooltip;
      chart.options._currencySymbol = config.options._currencySymbol;
      chart.options._privacyHidden = config.options._privacyHidden;
      chart.update('none');
    }
  });
</script>

<div class="chart-wrapper">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  .chart-wrapper {
    position: relative;
    width: 100%;
    height: 280px;
  }
</style>
