import { describe, it, expect } from 'vitest';
import { SERIES_COLORS } from '$lib/utils/chartColors.js';
import { BUCKET_COLORS } from '$lib/utils/strategy.js';
import { lighten } from '$lib/utils/neon.js';

describe('chart palette', () => {
  it('keeps a single series palette, starting with the dark blue and green', () => {
    expect(SERIES_COLORS).toHaveLength(10);
    expect(SERIES_COLORS[0]).toBe('#4263eb');
    expect(SERIES_COLORS[1]).toBe('#2f9e44');
    for (const color of SERIES_COLORS) expect(color).toMatch(/^#[0-9a-f]{6}$/);
  });

  it('uses the first five series colours for the strategy buckets', () => {
    expect(Object.values(BUCKET_COLORS).sort()).toEqual(SERIES_COLORS.slice(0, 5).sort());
  });

  it('mixes a colour towards white for the neon rim', () => {
    expect(lighten('#000000', 0.45)).toBe('#737373');
    expect(lighten('#ffffff')).toBe('#ffffff');
    expect(lighten('#00c2ff')).not.toBe('#00c2ff');
  });
});
