<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { segmentLabelsPlugin } from './segmentLabelsPlugin.js';

  Chart.register(...registerables);

  let { labels = [], data = [], colors = ['#4263eb', '#2f9e44', '#f08c00', '#e03131', '#845ef7', '#20c997', '#ff6b6b', '#339af0', '#94d82d', '#f06595'], currencySymbol = '' } = $props();

  let canvas;
  let chart;

  onMount(() => {
    const ctx = canvas.getContext('2d');
    chart = new Chart(ctx, {
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
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = ((ctx.parsed / total) * 100).toFixed(1);
                return ` ${ctx.label}: ${currencySymbol}${ctx.parsed.toLocaleString()} (${pct}%)`;
              },
            },
          },
        },
      },
      plugins: [segmentLabelsPlugin],
    });
  });

  onDestroy(() => {
    chart?.destroy();
    chart = null;
  });

  $effect(() => {
    if (chart?.canvas && canvas?.isConnected) {
      chart.data.labels = [...labels];
      chart.data.datasets[0].data = [...data];
      chart.data.datasets[0].backgroundColor = [...colors];
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
