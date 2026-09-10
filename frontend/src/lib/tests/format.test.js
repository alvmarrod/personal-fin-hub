import { describe, it, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { setDisplayTimezone } from '$lib/preferences/timezone.svelte';
import { privacyHidden, togglePrivacy } from '$lib/preferences/privacy.svelte';
import { formatDate, formatMonthYear, formatDateTime, formatAmount, maskAmount, MASK } from '$lib/utils/format.svelte';

describe('formatDate', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
    setDisplayTimezone('UTC');
  });

  it('formats with the selected locale (en-US)', () => {
    setDisplayTimezone('UTC');
    expect(formatDate('2025-01-15')).toBe(new Date('2025-01-15').toLocaleDateString('en-US', { timeZone: 'UTC' }));
  });

  it('formats with the selected locale (es-ES)', () => {
    setLocale('es-ES');
    setDisplayTimezone('UTC');
    expect(formatDate('2025-01-15')).toBe(new Date('2025-01-15').toLocaleDateString('es-ES', { timeZone: 'UTC' }));
  });

  it('returns a dash for empty values', () => {
    expect(formatDate(null)).toBe('-');
    expect(formatDate(undefined)).toBe('-');
    expect(formatDate('')).toBe('-');
  });
});

describe('formatMonthYear', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
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
});

describe('formatDateTime', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
    setDisplayTimezone('UTC');
  });

  it('formats in the display timezone', () => {
    setLocale('es-ES');
    setDisplayTimezone('UTC');
    expect(formatDateTime('2025-01-15T10:00:00Z')).toBe(
      new Date('2025-01-15T10:00:00Z').toLocaleString('es-ES', { timeZone: 'UTC' }),
    );
  });

  it('converts to the display timezone', () => {
    setDisplayTimezone('Asia/Tokyo');
    expect(formatDateTime('2025-01-15T00:00:00Z')).toBe(
      new Date('2025-01-15T00:00:00Z').toLocaleString('en-US', { timeZone: 'Asia/Tokyo' }),
    );
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