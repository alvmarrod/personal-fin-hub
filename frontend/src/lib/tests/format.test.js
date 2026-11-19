import { describe, it, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { setDisplayTimezone } from '$lib/preferences/timezone.svelte';
import { setDateFormat } from '$lib/preferences/dateFormat.svelte';
import { setNumberFormat } from '$lib/preferences/numberFormat.svelte';
import { privacyHidden, togglePrivacy } from '$lib/preferences/privacy.svelte';
import { formatDate, formatMonthYear, formatDateTime, formatAmount, formatPercent, maskAmount, MASK } from '$lib/utils/format.svelte';

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

  it('localizes the month name in Japanese', () => {
    setLocale('ja-JP');
    expect(formatMonthYear('2025-01-15')).toContain('2025年1月');
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

  it('uses a 24-hour clock in Japanese', () => {
    setLocale('ja-JP');
    setDisplayTimezone('UTC');
    const out = formatDateTime('2025-01-15T14:30:00Z');
    expect(out).toContain('14:30');
    expect(out).not.toContain('PM');
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
    setNumberFormat('dot-comma');
  });

  it('defaults to dot thousands and comma decimals', () => {
    expect(formatAmount(8340)).toBe('8.340');
    expect(formatAmount(9802.45)).toBe('9.802,45');
    expect(formatAmount(1234567)).toBe('1.234.567');
  });

  it('follows the comma-dot setting', () => {
    setNumberFormat('comma-dot');
    expect(formatAmount(8340)).toBe('8,340');
    expect(formatAmount(9802.45)).toBe('9,802.45');
    expect(formatAmount(1234567)).toBe('1,234,567');
  });

  it('does not follow the language locale', () => {
    setLocale('es-ES');
    setNumberFormat('comma-dot');
    expect(formatAmount(8340)).toBe('8,340');

    setLocale('en-US');
    setNumberFormat('dot-comma');
    expect(formatAmount(8340)).toBe('8.340');
  });

  it('hides a zero decimal part', () => {
    expect(formatAmount(43)).toBe('43');
    expect(formatAmount(43.0)).toBe('43');
    expect(formatAmount(12345.0)).toBe('12.345');
  });

  it('caps decimals at two for every magnitude', () => {
    expect(formatAmount(43.256)).toBe('43,26');
    expect(formatAmount(0.523)).toBe('0,52');
    expect(formatAmount(12345.678)).toBe('12.345,68');
  });

  it('applies the same rules to every currency', () => {
    expect(formatAmount(678841, 'JPY')).toBe('678.841');
    expect(formatAmount(43.25, 'JPY')).toBe('43,25');
  });

  it('returns a dash for empty values', () => {
    expect(formatAmount(null)).toBe('-');
    expect(formatAmount(undefined)).toBe('-');
    expect(formatAmount(Number.NaN)).toBe('-');
  });
});

describe('formatPercent', () => {
  afterEach(() => {
    cleanup();
    setNumberFormat('dot-comma');
  });

  it('fixes two decimals below one unit', () => {
    expect(formatPercent(0)).toBe('0.00%');
    expect(formatPercent(0.4)).toBe('0.40%');
    expect(formatPercent(0.004)).toBe('0.00%');
  });

  it('fixes one decimal from one to ten units', () => {
    expect(formatPercent(1)).toBe('1.0%');
    expect(formatPercent(5)).toBe('5.0%');
    expect(formatPercent(8.1)).toBe('8.1%');
    expect(formatPercent(0.995)).toBe('1.0%');
  });

  it('trims trailing zeros from ten units up', () => {
    expect(formatPercent(10)).toBe('10%');
    expect(formatPercent(12)).toBe('12%');
    expect(formatPercent(10.1)).toBe('10.1%');
    expect(formatPercent(13.15)).toBe('13.15%');
    expect(formatPercent(10.1)).not.toContain('10.10');
    expect(formatPercent(99.996)).toBe('100%');
  });

  it('classifies on the rounded value', () => {
    expect(formatPercent(9.96)).toBe('10.0%');
    expect(formatPercent(9.999)).toBe('10%');
  });

  it('separates thousands with a space', () => {
    expect(formatPercent(1234.5)).toBe('1 234.5%');
  });

  it('keeps a negative sign but never a negative zero', () => {
    expect(formatPercent(-5)).toBe('-5.0%');
    expect(formatPercent(-0.004)).toBe('0.00%');
  });

  it('adds a plus sign on request', () => {
    expect(formatPercent(5, { sign: true })).toBe('+5.0%');
    expect(formatPercent(-5, { sign: true })).toBe('-5.0%');
    expect(formatPercent(0, { sign: true })).toBe('0.00%');
  });

  it('ignores the number-format setting', () => {
    setNumberFormat('comma-dot');
    expect(formatPercent(13.15)).toBe('13.15%');
    expect(formatPercent(1234.5)).toBe('1 234.5%');
    setNumberFormat('dot-comma');
    expect(formatPercent(13.15)).toBe('13.15%');
  });

  it('returns a dash for empty values', () => {
    expect(formatPercent(null)).toBe('-');
    expect(formatPercent(undefined)).toBe('-');
    expect(formatPercent(Number.NaN)).toBe('-');
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
