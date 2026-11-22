<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { segmentLabelsPlugin } from './segmentLabelsPlugin.js';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { formatAmount, formatPercent, MASK } from '$lib/utils/format.svelte';
  import { NEON_COLORS, lighten, neonArcGlowPlugin } from '$lib/utils/neon.js';

  Chart.register(...registerables);

  let { labels = [], data = [], colors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'], currencySymbol = '', neon = false } = $props();

  let activeColors = $derived(neon ? NEON_COLORS : colors);

  let canvas;
  let chart;

  function buildChartConfig() {
    return {
      type: 'pie',
      data: {
        labels: [...labels],
        datasets: [{
          data: [...data],
          backgroundColor: [...activeColors],
          borderWidth: 2,
          borderColor: neon ? activeColors.map((color) => lighten(color)) : '#ffffff',
          spacing: neon ? 2 : 0,
          hoverOffset: neon ? 8 : 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
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
                const pct = total > 0 ? (ctx.parsed / total) * 100 : 0;
                return ` ${ctx.label}: ${currencySymbol}${formatAmount(ctx.parsed)} (${formatPercent(pct)})`;
              },
            },
          },
        },
      },
      plugins: neon ? [segmentLabelsPlugin, neonArcGlowPlugin] : [segmentLabelsPlugin],
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
      chart.data.datasets[0].backgroundColor = [...activeColors];
      chart.data.datasets[0].borderColor = neon ? activeColors.map((color) => lighten(color)) : '#ffffff';
      chart.data.datasets[0].spacing = neon ? 2 : 0;
      chart.data.datasets[0].hoverOffset = neon ? 8 : 0;
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
