<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';

  Chart.register(...registerables);

  let { labels = [], datasets = [], height = 300 } = $props();

  let canvas;
  let chart;

  const defaultColors = [
    '#4263eb', '#2f9e44', '#f08c00', '#e03131',
    '#845ef7', '#20c997', '#ff6b6b', '#339af0',
    '#94d82d', '#f06595',
  ];

  function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function buildChartConfig() {
    return {
      type: 'line',
      data: {
        labels: [...labels],
        datasets: datasets.map((d, i) => {
          const color = d.color || defaultColors[i % defaultColors.length];
          return {
            label: d.label || `Series ${i + 1}`,
            data: [...d.data],
            borderColor: color,
            backgroundColor: hexToRgba(color, 0.4),
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2,
          };
        }),
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
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { maxTicksLimit: 12, color: '#6c757d', font: { size: 11 } },
            grid: { display: false },
          },
          y: {
            stacked: true,
            ticks: {
              color: '#6c757d',
              font: { size: 11 },
              callback: (v) => v.toLocaleString(),
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
  });

  $effect(() => {
    if (chart) {
      const config = buildChartConfig();
      chart.data.labels = config.data.labels;
      chart.data.datasets = config.data.datasets;
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
