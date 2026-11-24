/**
 * Neon palettes and canvas glow helpers for the dashboard charts.
 *
 * The effect is confined to the drawing: the white card, axes, labels and
 * layout stay untouched.
 */

import { BUCKET_COLORS } from './strategy.js';

/** Mix a `#rrggbb` colour with white. Used for the neon segment rims. */
export function lighten(hex, amount = 0.45) {
  const value = Number.parseInt(hex.slice(1), 16);
  const mix = (channel) => Math.round(channel + (255 - channel) * amount);
  const r = mix((value >> 16) & 255);
  const g = mix((value >> 8) & 255);
  const b = mix(value & 255);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

/** Draw a soft glow behind every pie/doughnut arc, in the arc's own colour. */
export const neonArcGlowPlugin = {
  id: 'neonArcGlow',
  beforeDatasetDraw(chart) {
    const dataset = chart.data.datasets[0];
    const meta = chart.getDatasetMeta(0);
    if (!dataset?.backgroundColor || !Array.isArray(dataset.backgroundColor) || !meta?.data) return;
    const { ctx } = chart;
    ctx.save();
    ctx.globalAlpha = 0.4;
    meta.data.forEach((arc, index) => {
      const color = dataset.backgroundColor[index];
      if (!arc || !color) return;
      ctx.beginPath();
      ctx.arc(arc.x, arc.y, arc.outerRadius, arc.startAngle, arc.endAngle);
      ctx.strokeStyle = color;
      ctx.lineWidth = 4;
      ctx.shadowColor = color;
      ctx.shadowBlur = 10;
      ctx.stroke();
    });
    ctx.restore();
  },
};

/** Draw a halo behind every bubble, in the bucket's neon colour. */
export const neonBubbleGlowPlugin = {
  id: 'neonBubbleGlow',
  beforeDatasetsDraw(chart) {
    const dataset = chart.data.datasets[0];
    const meta = chart.getDatasetMeta(0);
    if (!dataset?.data || !meta?.data) return;
    const { ctx } = chart;
    ctx.save();
    dataset.data.forEach((point, index) => {
      const el = meta.data[index];
      if (!el) return;
      const color = BUCKET_COLORS[point.bucket] ?? '#4263eb';
      ctx.beginPath();
      ctx.arc(el.x, el.y, point.r ?? 8, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.15;
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.globalAlpha = 1;
    });
    ctx.restore();
  },
};
