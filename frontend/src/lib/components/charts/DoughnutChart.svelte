<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { segmentLabelsPlugin } from './segmentLabelsPlugin.js';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { formatAmount, formatPercent, MASK } from '$lib/utils/format.svelte';
  import { SERIES_COLORS } from '$lib/utils/chartColors.js';
  import { lighten, neonArcGlowPlugin } from '$lib/utils/neon.js';

  Chart.register(...registerables);

  let { labels = [], data = [], colors = SERIES_COLORS, currencySymbol = '', tooltipExtra = [], neon = false } = $props();


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
          borderColor: neon ? colors.map((color) => lighten(color, 0.3)) : '#ffffff',
          spacing: neon ? 2 : 0,
          hoverOffset: neon ? 8 : 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '60%',
        layout: { padding: 16 },
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
                const lines = [` ${ctx.label}: ${currencySymbol}${formatAmount(ctx.parsed)} (${formatPercent(pct)})`];
                const extra = tooltipExtra?.[ctx.dataIndex];
                if (extra) lines.push(` ${extra}`);
                return lines;
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
      chart.data.datasets[0].backgroundColor = [...colors];
      chart.data.datasets[0].borderColor = neon ? colors.map((color) => lighten(color, 0.3)) : '#ffffff';
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
