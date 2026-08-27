import { locale } from '$lib/i18n/index.svelte';

export function formatDate(value: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions): string {
  if (value === null || value === undefined || value === '') return '-';
  return new Date(value).toLocaleDateString(locale(), options);
}

export function formatMonthYear(value: Date | string | number): string {
  return formatDate(value, { month: 'long', year: 'numeric' });
}

export function formatDateTime(value: Date | string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-';
  return new Date(value).toLocaleString(locale());
}