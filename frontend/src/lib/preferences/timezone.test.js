import { describe, it, expect, beforeEach } from 'vitest';
import { setDisplayTimezone, formatTimestamp } from './timezone.svelte';

describe('formatTimestamp', () => {
  beforeEach(() => {
    setDisplayTimezone('UTC');
  });

  it('returns dash for null', () => {
    expect(formatTimestamp(null)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(formatTimestamp(undefined)).toBe('-');
  });

  it('returns input as-is for unparseable strings', () => {
    expect(formatTimestamp('not-a-date')).toBe('not-a-date');
  });

  it('formats date and time by default', () => {
    const result = formatTimestamp('2024-06-15T14:30:00Z');
    expect(result).toContain('2024-06-15');
    expect(result).toContain('14:30');
  });

  it('formats date only', () => {
    const result = formatTimestamp('2024-06-15T14:30:00Z', { time: false });
    expect(result).toBe('2024-06-15');
  });

  it('formats time only', () => {
    const result = formatTimestamp('2024-06-15T14:30:00Z', { date: false });
    expect(result).toBe('14:30');
  });

  it('includes seconds when requested', () => {
    const result = formatTimestamp('2024-06-15T14:30:45', { seconds: true });
    expect(result).toContain(':45');
  });

  it('handles Z-suffixed timestamps', () => {
    const result = formatTimestamp('2024-06-15T14:30:00Z');
    expect(result).toContain('2024-06-15');
    expect(result).toContain('14:30');
  });

  it('converts to selected timezone', () => {
    setDisplayTimezone('Asia/Tokyo');
    const result = formatTimestamp('2024-06-15T14:30:00Z');
    // 14:30 UTC = 23:30 JST
    expect(result).toContain('23:30');
  });
});
