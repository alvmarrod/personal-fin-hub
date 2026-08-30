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

type MoneyFormatOptions = Intl.NumberFormatOptions & { minimumGroupingDigits?: number };

export function formatAmount(value: number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const abs = Math.abs(value);
  const decimals =
    currency === 'JPY'
      ? abs >= 10_000
        ? 0
        : 2
      : abs >= 1_000
        ? 0
        : abs >= 1
          ? 2
          : 3;
  const options: MoneyFormatOptions = {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
    useGrouping: true,
    minimumGroupingDigits: 1,
  };
  return new Intl.NumberFormat(locale(), options).format(value);
}