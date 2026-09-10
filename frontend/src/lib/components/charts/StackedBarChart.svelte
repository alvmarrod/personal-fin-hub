<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { MASK } from '$lib/utils/format.svelte';

  Chart.register(...registerables);

  let { labels = [], datasets = [], height = 300, currencySymbol = '' } = $props();

  let canvas;
  let chart;

  const defaultColors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'];

  function mapDatasets(ds) {
    return ds.map((d, i) => ({
      label: d.label,
      data: [...d.data],
      backgroundColor: d.color || defaultColors[i % defaultColors.length],
      ...(d.stack !== undefined && { stack: d.stack }),
    }));
  }

  function buildChartConfig() {
    return {
      type: 'bar',
      data: {
        labels: [...labels],
        datasets: mapDatasets(datasets),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => privacyHidden()
                ? ` ${ctx.dataset.label}: ${MASK}${currencySymbol}`
                : ` ${ctx.dataset.label}: ${currencySymbol}${ctx.parsed.y.toLocaleString()}`,
            },
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { maxTicksLimit: 12, color: '#6c757d', font: { size: 11 } },
            grid: { display: false },
          },
          y: {
            stacked: true,
            ticks: {
              color: '#6c757d',
              font: { size: 11 },
              callback: (v) => (privacyHidden() ? MASK : v.toLocaleString()),
            },
            grid: { color: 'rgba(0,0,0,0.05)' },
          },
        },
        interaction: {
          intersect: false,
          mode: 'index',
        },
      },
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
      chart.data.datasets = mapDatasets(datasets);
      chart.options.scales = config.options.scales;
      chart.options.plugins.tooltip = config.options.plugins.tooltip;
      chart.update('none');
    }
  });
</script>

<div class="chart-wrapper" style="height: {height}px">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  .chart-wrapper {
    position: relative;
    width: 100%;
  }
</style>
