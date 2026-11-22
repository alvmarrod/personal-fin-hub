import { describe, it, expect } from 'vitest';
import { NEON_COLORS, NEON_BUCKET_COLORS, lighten } from '$lib/utils/neon.js';

describe('neon palette', () => {
  it('defines ten hex colours', () => {
    expect(NEON_COLORS).toHaveLength(10);
    for (const color of NEON_COLORS) expect(color).toMatch(/^#[0-9a-f]{6}$/);
  });

  it('covers the five strategy buckets', () => {
    expect(Object.keys(NEON_BUCKET_COLORS).sort()).toEqual([
      'bonds',
      'cash',
      'equities',
      'gold',
      'real_estate',
    ]);
  });

  it('mixes a colour towards white for the segment rim', () => {
    expect(lighten('#000000')).toBe('#737373');
    expect(lighten('#ffffff')).toBe('#ffffff');
    expect(lighten('#00c2ff')).not.toBe('#00c2ff');
  });
});
