<script>
  import { Chart, registerables } from 'chart.js';
  import { onMount, onDestroy } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { formatPercent } from '$lib/utils/format.svelte';
  import { BUCKET_COLORS, bucketLabel } from '$lib/utils/strategy.js';
  import { neonBubbleGlowPlugin } from '$lib/utils/neon.js';

  Chart.register(...registerables);

  let { points = [], height = 300 } = $props();

  let canvas;
  let chart;

  const GREEN = '#2f9e44';
  const RED = '#e03131';

  function haloText(ctx, text, x, y, color) {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)';
    ctx.lineWidth = 3;
    ctx.strokeText(text, x, y);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }

  const deviationPlugin = {
    id: 'strategyDeviation',
    beforeDatasetsDraw(current) {
      const { ctx, scales } = current;
      ctx.save();

      ctx.beginPath();
      ctx.moveTo(scales.x.getPixelForValue(0), scales.y.getPixelForValue(0));
      ctx.lineTo(scales.x.getPixelForValue(100), scales.y.getPixelForValue(100));
      ctx.strokeStyle = GREEN;
      ctx.lineWidth = 2;
      ctx.shadowColor = GREEN;
      ctx.shadowBlur = 8;
      ctx.stroke();

      for (const raw of current.data.datasets[0].data) {
        const x = scales.x.getPixelForValue(raw.x);
        const y = scales.y.getPixelForValue(raw.y);
        const yTarget = scales.y.getPixelForValue(raw.x);
        if (y === yTarget) continue;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, yTarget);
        ctx.strokeStyle = RED;
        ctx.lineWidth = 2;
        ctx.shadowColor = RED;
        ctx.shadowBlur = 7;
        ctx.stroke();
      }

      ctx.restore();
    },
    afterDatasetsDraw(current) {
      const { ctx, scales } = current;
      ctx.save();
      ctx.font = '10px system-ui, sans-serif';
      ctx.textBaseline = 'middle';

      for (const raw of current.data.datasets[0].data) {
        const x = scales.x.getPixelForValue(raw.x);
        const y = scales.y.getPixelForValue(raw.y);
        const right = raw.x <= 75;

        ctx.textAlign = right ? 'left' : 'right';
        haloText(ctx, bucketLabel(raw.bucket), x + (right ? raw.r + 4 : -(raw.r + 4)), y, '#212529');
      }

      ctx.restore();
    },
  };

  function dataset() {
    return {
      data: points.map((point) => ({ ...point })),
      backgroundColor: points.map((point) => `${BUCKET_COLORS[point.bucket] ?? '#4263eb'}cc`),
      borderColor: points.map((point) => BUCKET_COLORS[point.bucket] ?? '#4263eb'),
      borderWidth: 2,
    };
  }

  function buildConfig() {
    return {
      type: 'bubble',
      data: { datasets: [dataset()] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 8, right: 12, bottom: 4, left: 4 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => bucketLabel(items[0].raw.bucket),
              label: (ctx) => [
                `${t('strategy.colTarget')}: ${formatPercent(ctx.raw.x)}`,
                `${t('strategy.colActual')}: ${formatPercent(ctx.raw.y)}`,
                `${t('strategy.colDrift')}: ${formatPercent(ctx.raw.drift, { sign: true })}`,
              ],
            },
          },
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            title: { display: true, text: `${t('strategy.colTarget')} %`, color: '#6c757d', font: { size: 10 } },
            ticks: { color: '#6c757d', font: { size: 10 }, callback: (v) => `${v}%` },
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
          },
          y: {
            min: 0,
            max: 100,
            title: { display: true, text: `${t('strategy.colActual')} %`, color: '#6c757d', font: { size: 10 } },
            ticks: { color: '#6c757d', font: { size: 10 }, callback: (v) => `${v}%` },
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
          },
        },
      },
      plugins: [neonBubbleGlowPlugin, deviationPlugin],
    };
  }

  onMount(() => {
    chart = new Chart(canvas.getContext('2d'), buildConfig());
  });

  onDestroy(() => {
    chart?.destroy();
    chart = null;
  });

  $effect(() => {
    if (!chart) return;
    chart.data.datasets[0] = dataset();
    chart.update('none');
  });
</script>

<div class="bubble-wrapper" style="height: {height}px" role="img" aria-label={t('dashboard.targetVsActual')}>
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  .bubble-wrapper {
    width: 100%;
  }
</style>
