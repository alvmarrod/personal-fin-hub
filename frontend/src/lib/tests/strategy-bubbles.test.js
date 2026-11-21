import { describe, it, expect } from 'vitest';
import { bubblePoints, driftText, hiddenOnTarget } from '$lib/utils/strategy.js';

const BUCKETS = [
  { bucket: 'equities', target_pct: 55, share_pct: 62, drift_pp: 7 },
  { bucket: 'bonds', target_pct: 30, share_pct: 24, drift_pp: -6 },
  { bucket: 'real_estate', target_pct: 0, share_pct: 0, drift_pp: 0 },
  { bucket: 'gold', target_pct: 0, share_pct: 0, drift_pp: 0 },
];

describe('bubblePoints', () => {
  it('drops buckets that are at 0% target and 0% actual', () => {
    const points = bubblePoints(BUCKETS);
    expect(points.map((point) => point.bucket)).toEqual(['equities', 'bonds']);
  });

  it('maps target to x, actual to y and keeps the drift', () => {
    const [equities] = bubblePoints(BUCKETS);
    expect(equities.x).toBe(55);
    expect(equities.y).toBe(62);
    expect(equities.drift).toBe(7);
  });

  it('sizes the bubble from the actual share', () => {
    const [equities, bonds] = bubblePoints(BUCKETS);
    expect(equities.r).toBeGreaterThan(bonds.r);
  });

  it('bounds the radius to 5–14 px', () => {
    const points = bubblePoints([
      { bucket: 'equities', target_pct: 100, share_pct: 100, drift_pp: 0 },
      { bucket: 'bonds', target_pct: 0, share_pct: 1, drift_pp: 0 },
    ]);
    const [equities, bonds] = points;
    expect(equities.r).toBe(14);
    expect(bonds.r).toBeGreaterThanOrEqual(5);
    expect(bonds.r).toBeLessThan(14);
  });

  it('handles empty input', () => {
    expect(bubblePoints([])).toEqual([]);
    expect(bubblePoints(null)).toEqual([]);
  });
});

describe('hiddenOnTarget', () => {
  it('counts buckets at 0% on both sides', () => {
    expect(hiddenOnTarget(BUCKETS)).toBe(2);
    expect(hiddenOnTarget([])).toBe(0);
  });
});

describe('driftText', () => {
  it('renders a signed difference as a percentage', () => {
    expect(driftText(7)).toBe('+7.0%');
    expect(driftText(-6)).toBe('-6.0%');
  });

  it('uses the configured precision for small values', () => {
    expect(driftText(0.4)).toBe('+0.40%');
    expect(driftText(0)).toBe('0.00%');
  });

  it('renders a dash for missing values', () => {
    expect(driftText(null)).toBe('—');
    expect(driftText(undefined)).toBe('—');
  });
});
