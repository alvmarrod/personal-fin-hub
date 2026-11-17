import { describe, it, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { setDisplayTimezone } from '$lib/preferences/timezone.svelte';
import { setDateFormat } from '$lib/preferences/dateFormat.svelte';
import { privacyHidden, togglePrivacy } from '$lib/preferences/privacy.svelte';
import { formatDate, formatMonthYear, formatDateTime, formatAmount, maskAmount, MASK } from '$lib/utils/format.svelte';

describe('formatDate', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
    setDisplayTimezone('UTC');
    setDateFormat('dmy');
  });

  it('defaults to zero-padded day/month/year', () => {
    expect(formatDate('2025-03-15')).toBe('15/03/2025');
    expect(formatDate('2025-01-05')).toBe('05/01/2025');
  });

  it('follows month/day/year when selected, regardless of language', () => {
    setDateFormat('mdy');
    setLocale('es-ES');
    expect(formatDate('2025-03-15')).toBe('03/15/2025');
  });

  it('follows ISO when selected', () => {
    setDateFormat('iso');
    expect(formatDate('2025-03-15')).toBe('2025-03-15');
  });

  it('reads a bare calendar date without shifting it', () => {
    setDisplayTimezone('America/Los_Angeles');
    expect(formatDate('2025-03-15')).toBe('15/03/2025');
  });

  it('converts timestamps to the display timezone', () => {
    setDisplayTimezone('Asia/Tokyo');
    expect(formatDate('2025-01-15T00:00:00Z')).toBe('15/01/2025');
    setDisplayTimezone('America/Los_Angeles');
    expect(formatDate('2025-01-15T00:00:00Z')).toBe('14/01/2025');
  });

  it('keeps the short month/day shape and applies the order', () => {
    expect(formatDate('2025-03-05T12:00:00Z', { month: 'short', day: 'numeric' })).toBe('05 Mar');
    setDateFormat('mdy');
    expect(formatDate('2025-03-05T12:00:00Z', { month: 'short', day: 'numeric' })).toBe('Mar 05');
    setDateFormat('iso');
    expect(formatDate('2025-03-05T12:00:00Z', { month: 'short', day: 'numeric' })).toBe('03-05');
  });

  it('returns a dash for empty or unparseable values', () => {
    expect(formatDate(null)).toBe('-');
    expect(formatDate(undefined)).toBe('-');
    expect(formatDate('')).toBe('-');
    expect(formatDate('not-a-date')).toBe('-');
  });
});

describe('formatMonthYear', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
    setDateFormat('dmy');
  });

  it('renders English month and year', () => {
    expect(formatMonthYear('2025-01-15')).toContain('January');
    expect(formatMonthYear('2025-01-15')).toContain('2025');
  });

  it('renders Spanish month and year', () => {
    setLocale('es-ES');
    expect(formatMonthYear('2025-01-15')).toContain('enero');
    expect(formatMonthYear('2025-01-15')).toContain('2025');
  });

  it('does not depend on the date order setting', () => {
    setDateFormat('iso');
    expect(formatMonthYear('2025-01-15')).toContain('January');
  });
});

describe('formatDateTime', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
    setDisplayTimezone('UTC');
    setDateFormat('dmy');
  });

  it('joins the chosen date order with the localized time', () => {
    const out = formatDateTime('2025-01-15T10:00:00Z');
    expect(out).toContain('15/01/2025');
    expect(out).toContain('10:00:00');
  });

  it('uses the selected order', () => {
    setDateFormat('iso');
    const out = formatDateTime('2025-01-15T10:00:00Z');
    expect(out).toContain('2025-01-15');
    expect(out).toContain('10:00:00');
  });

  it('converts to the display timezone', () => {
    setDisplayTimezone('Asia/Tokyo');
    const out = formatDateTime('2025-01-15T14:30:00Z');
    expect(out).toContain('15/01/2025');
    expect(out).toContain('11:30');
  });

  it('uses a 24-hour clock in a 24-hour locale', () => {
    setLocale('es-ES');
    setDisplayTimezone('Asia/Tokyo');
    const out = formatDateTime('2025-01-15T14:30:00Z');
    expect(out).toContain('15/01/2025');
    expect(out).toContain('23:30');
  });

  it('returns a dash for empty values', () => {
    expect(formatDateTime(null)).toBe('-');
    expect(formatDateTime(undefined)).toBe('-');
    expect(formatDateTime('')).toBe('-');
  });
});

describe('formatAmount', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
  });

  it('groups thousands in es-ES below the locale default (e.g. 8.340 JPY)', () => {
    setLocale('es-ES');
    expect(formatAmount(8340, 'JPY')).toBe('8.340');
    expect(formatAmount(9802.45, 'JPY')).toBe('9.802,45');
  });

  it('groups thousands in en-US', () => {
    expect(formatAmount(8340, 'JPY')).toBe('8,340');
    expect(formatAmount(1234567, 'EUR')).toBe('1,234,567');
  });

  it('uses 0 decimals for large JPY and 2 for small JPY', () => {
    expect(formatAmount(678841, 'JPY')).toBe('678,841');
    expect(formatAmount(43, 'JPY')).toBe('43');
    expect(formatAmount(43.25, 'JPY')).toBe('43.25');
  });

  it('uses 0 decimals for large non-JPY and 2 for small', () => {
    expect(formatAmount(1234.56, 'EUR')).toBe('1,235');
    expect(formatAmount(14.53, 'EUR')).toBe('14.53');
  });

  it('uses 3 decimals for sub-1 values', () => {
    expect(formatAmount(0.523, 'USD')).toBe('0.523');
  });

  it('returns a dash for empty values', () => {
    expect(formatAmount(null)).toBe('-');
    expect(formatAmount(undefined)).toBe('-');
    expect(formatAmount(Number.NaN)).toBe('-');
  });
});

describe('maskAmount', () => {
  afterEach(() => {
    cleanup();
    while (privacyHidden()) {
      togglePrivacy();
    }
  });

  it('returns the formatted value when privacy is visible', () => {
    expect(maskAmount('1,234')).toBe('1,234');
  });

  it('returns the mask when privacy is hidden', () => {
    togglePrivacy();
    expect(maskAmount('1,234')).toBe(MASK);
  });

  it('appends the currency symbol to the mask', () => {
    togglePrivacy();
    expect(maskAmount('1,234', '¥')).toBe(`${MASK}¥`);
  });

  it('masks empty values too when hidden', () => {
    togglePrivacy();
    expect(maskAmount(null)).toBe(MASK);
  });

  it('returns undefined for empty values when visible', () => {
    expect(maskAmount(null)).toBe(undefined);
  });
});
