export const segmentLabelsPlugin = {
  id: 'segmentLabels',
  afterDraw(chart) {
    const { ctx, data: chartData } = chart;
    const dataset = chartData.datasets[0];
    const meta = chart.getDatasetMeta(0);
    const total = dataset.data.reduce((a, b) => a + b, 0);
    if (total === 0) return;

    const currencySymbol = chart.options._currencySymbol || '';

    ctx.save();
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    meta.data.forEach((arc, i) => {
      const value = dataset.data[i];
      if (value === 0) return;

      const pct = ((value / total) * 100).toFixed(1);
      if (parseFloat(pct) < 5) return;

      const angle = (arc.startAngle + arc.endAngle) / 2;
      const outerRadius = arc.outerRadius * 0.75;
      const x = arc.x + Math.cos(angle) * outerRadius;
      const y = arc.y + Math.sin(angle) * outerRadius;

      ctx.fillStyle = '#fff';
      ctx.fillText(`${pct}%`, x, y - 6);
      ctx.font = '9px sans-serif';
      const shortValue = value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0);
      ctx.fillText(`${currencySymbol}${shortValue}`, x, y + 7);
    });

    ctx.restore();
  },
};
