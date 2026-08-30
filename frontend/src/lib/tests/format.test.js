import { describe, it, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { formatDate, formatMonthYear, formatDateTime, formatAmount } from '$lib/utils/format.svelte';

describe('formatDate', () => {
  afterEach(() => {
    cleanup();
    setLocale('en-US');
  });

  it('formats with the selected locale (en-US)', () => {
    expect(formatDate('2025-01-15')).toBe(new Date('2025-01-15').toLocaleDateString('en-US'));
  });

  it('formats with the selected locale (es-ES)', () => {
    setLocale('es-ES');
    expect(formatDate('2025-01-15')).toBe(new Date('2025-01-15').toLocaleDateString('es-ES'));
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
  });

  it('formats with the selected locale', () => {
    setLocale('es-ES');
    expect(formatDateTime('2025-01-15T10:00:00Z')).toBe(new Date('2025-01-15T10:00:00Z').toLocaleString('es-ES'));
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