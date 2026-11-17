import { locale } from '$lib/i18n/index.svelte';
import { displayTimezone } from '$lib/preferences/timezone.svelte';
import { dateFormat } from '$lib/preferences/dateFormat.svelte';
import { privacyHidden } from '$lib/preferences/privacy.svelte';
import { parseUtc } from '$lib/utils/time.js';

export const MASK = '********';

export function maskAmount(formattedValue: string | null | undefined, currencySymbol?: string): string | undefined {
  if (!privacyHidden()) return formattedValue ?? undefined;
  return currencySymbol ? `${MASK}${currencySymbol}` : MASK;
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function zoneFor(value: Date | string | number): string {
  // A bare calendar date carries no time: read it in UTC so a display
  // timezone west of UTC cannot shift it to the previous day.
  return typeof value === 'string' && DATE_ONLY.test(value) ? 'UTC' : displayTimezone();
}

function dateParts(value: Date | string | number, timeZone: string): { day: string; month: string; year: string } {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(parseUtc(value)));
  const pick = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return { day: pick('day'), month: pick('month'), year: pick('year') };
}

/**
 * Render a date in the user's chosen order (DD/MM/YYYY by default), never in
 * the language locale's order. Month names are still localized.
 */
export function formatDate(value: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions): string {
  if (value === null || value === undefined || value === '') return '-';
  const date = new Date(parseUtc(value));
  if (Number.isNaN(date.getTime())) return '-';
  const timeZone = zoneFor(value);

  // Month names carry no day/month order, so Intl keeps them verbatim
  // ("January 2025", "enero de 2025").
  if (options?.month && options.month !== '2-digit' && options.month !== 'numeric' && !options.day) {
    return date.toLocaleDateString(locale(), { timeZone, ...options });
  }

  const { day, month, year } = dateParts(value, timeZone);
  const order = dateFormat();

  // Day + month only (chart axes): keep the short shape, fix the order.
  if (options?.day && options.month) {
    const monthLabel =
      options.month === 'short' || options.month === 'long'
        ? new Intl.DateTimeFormat(locale(), { timeZone, month: options.month }).format(date)
        : month;
    if (order === 'mdy') return `${monthLabel} ${day}`;
    if (order === 'iso') return `${month}-${day}`;
    return `${day} ${monthLabel}`;
  }

  if (order === 'mdy') return `${month}/${day}/${year}`;
  if (order === 'iso') return `${year}-${month}-${day}`;
  return `${day}/${month}/${year}`;
}

export function formatMonthYear(value: Date | string | number): string {
  return formatDate(value, { month: 'long', year: 'numeric' });
}

export function formatDateTime(value: Date | string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-';
  const date = new Date(parseUtc(value));
  if (Number.isNaN(date.getTime())) return '-';
  const time = date.toLocaleTimeString(locale(), {
    timeZone: zoneFor(value),
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  return `${formatDate(value)} ${time}`;
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

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const decimals = Math.abs(value) < 10 ? 4 : 2;
  const options: MoneyFormatOptions = {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: true,
    minimumGroupingDigits: 1,
  };
  return new Intl.NumberFormat(locale(), options).format(value);
}