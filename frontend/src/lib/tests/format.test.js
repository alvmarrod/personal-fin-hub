import { describe, it, expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import { formatDate, formatMonthYear, formatDateTime } from '$lib/utils/format.svelte';

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