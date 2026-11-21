<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { formatAmount, formatPercent, MASK } from '$lib/utils/format.svelte';

  Chart.register(...registerables);

  let { labels = [], datasets = [], height = 300, currencySymbol = '', fitToRange = false, unit = 'amount', maskable = true, showLegend = true } = $props();

  let canvas;
  let chart;

  const defaultColors = [
    '#4263eb', '#2f9e44', '#f08c00', '#e03131',
    '#845ef7', '#20c997', '#ff6b6b', '#339af0',
    '#94d82d', '#f06595',
  ];

  let isPercent = $derived(unit === 'percent');
  let hideValues = $derived(maskable && privacyHidden());

  function tick(v) {
    if (hideValues) return MASK;
    return isPercent ? formatPercent(v) : formatAmount(v);
  }

  function buildChartConfig() {
    const hasRightAxis = datasets.some(d => d.axis === 'right');
    const yRange = isPercent ? { min: 0, max: 100 } : fitToRange ? {} : { min: 0 };

    const scales = {
      x: {
        ticks: { maxTicksLimit: 10, color: '#6c757d', font: { size: 11 } },
        grid: { display: false },
      },
      y: {
        type: 'linear',
        position: 'left',
        ...yRange,
        ticks: {
          color: '#6c757d',
          font: { size: 11 },
          callback: tick,
        },
        grid: { color: 'rgba(0,0,0,0.05)' },
      },
    };

    if (hasRightAxis) {
      scales.y1 = {
        type: 'linear',
        position: 'right',
        ticks: {
          color: '#6c757d',
          font: { size: 11 },
          callback: tick,
        },
        grid: { drawOnChartArea: false },
      };
    }

    return {
      type: 'line',
      data: {
        labels: [...labels],
        datasets: datasets.map((d, i) => ({
          label: d.label || `Series ${i + 1}`,
          data: [...d.data],
          yAxisID: d.axis === 'right' ? 'y1' : 'y',
          borderColor: d.color || defaultColors[i % defaultColors.length],
          backgroundColor: 'transparent',
          fill: false,
          tension: 0.3,
          pointRadius: 2,
          pointHoverRadius: 5,
          borderWidth: 2,
          borderDash: d.dashed ? [6, 4] : undefined,
          stepped: d.stepped || false,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: showLegend && datasets.length > 1,
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (hideValues) return ` ${ctx.dataset.label}: ${MASK}${currencySymbol}`;
                if (ctx.parsed.y === null || ctx.parsed.y === undefined) {
                  return ` ${ctx.dataset.label}: —`;
                }
                return ` ${ctx.dataset.label}: ${
                  isPercent ? formatPercent(ctx.parsed.y) : `${currencySymbol}${formatAmount(ctx.parsed.y)}`
                }`;
              },
            },
          },
        },
        scales,
        interaction: { intersect: false, mode: 'index' },
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
      chart.data.labels = config.data.labels;
      chart.data.datasets = config.data.datasets;
      chart.options.scales = config.options.scales;
      chart.options.plugins.tooltip = config.options.plugins.tooltip;
      chart.options.plugins.legend.display = config.options.plugins.legend.display;
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
