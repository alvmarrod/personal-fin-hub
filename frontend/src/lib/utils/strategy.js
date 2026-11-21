import { t } from '$lib/i18n/index.svelte';
import { formatPercent } from '$lib/utils/format.svelte';

/** Fixed policy buckets. The mapping from asset class lives in the backend. */
export const STRATEGY_BUCKETS = ['equities', 'bonds', 'cash', 'real_estate', 'gold'];

/** Shared colours so the timeline, history and dashboard agree. */
export const BUCKET_COLORS = {
  equities: '#4263eb',
  bonds: '#2f9e44',
  cash: '#f08c00',
  real_estate: '#845ef7',
  gold: '#e03131',
};

/** @param {string} bucket */
export function bucketLabel(bucket) {
  return t(`bucket.${bucket}`);
}

/** @returns {Record<string, number>} */
export function emptyTargets() {
  return Object.fromEntries(STRATEGY_BUCKETS.map((bucket) => [bucket, 0]));
}

/** A signed difference in percentage points, e.g. `+7.0 pp`. */
export function driftText(value) {
  if (value === null || value === undefined) return '—';
  return `${formatPercent(value, { sign: true }).slice(0, -1)} pp`;
}

/**
 * Bubble data for the dashboard: target on x, actual on y, radius from the
 * actual share. Buckets at 0% target and 0% actual are dropped (they would
 * stack on the origin) and counted separately.
 *
 * @param {Array<{ bucket: string, target_pct?: number, share_pct?: number, drift_pp?: number }>} buckets
 */
export function bubblePoints(buckets) {
  return (buckets ?? [])
    .filter((bucket) => !((bucket.target_pct ?? 0) === 0 && (bucket.share_pct ?? 0) === 0))
    .map((bucket) => ({
      bucket: bucket.bucket,
      x: bucket.target_pct ?? 0,
      y: bucket.share_pct ?? 0,
      drift: bucket.drift_pp ?? 0,
      r: 6 + Math.sqrt(Math.max(bucket.share_pct ?? 0, 0)) * 2,
    }));
}

/** @param {Array<{ target_pct?: number, share_pct?: number }>} buckets */
export function hiddenOnTarget(buckets) {
  return (buckets ?? []).filter(
    (bucket) => (bucket.target_pct ?? 0) === 0 && (bucket.share_pct ?? 0) === 0,
  ).length;
}
