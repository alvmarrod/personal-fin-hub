import { locale } from '$lib/i18n/index.svelte';
import { displayTimezone } from '$lib/preferences/timezone.svelte';
import { dateFormat } from '$lib/preferences/dateFormat.svelte';
import { privacyHidden } from '$lib/preferences/privacy.svelte';
import { numberFormat, type NumberFormat } from '$lib/preferences/numberFormat.svelte';
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

// Fixed locales give the exact separators the setting asks for, independent of
// the UI language. Cached per (setup, decimals) — these run in every table cell.
const NUMBER_LOCALES: Record<NumberFormat, string> = {
  'comma-dot': 'en-US',
  'dot-comma': 'de-DE',
};
const _formatters = new Map<string, Intl.NumberFormat>();

function numberFormatter(min: number, max: number): Intl.NumberFormat {
  const style = numberFormat();
  const key = `${style}:${min}:${max}`;
  let formatter = _formatters.get(key);
  if (!formatter) {
    const options: MoneyFormatOptions = {
      minimumFractionDigits: min,
      maximumFractionDigits: max,
      useGrouping: true,
      minimumGroupingDigits: 1,
    };
    formatter = new Intl.NumberFormat(NUMBER_LOCALES[style], options);
    _formatters.set(key, formatter);
  }
  return formatter;
}

/**
 * Format a currency amount with the user's separator setting. Trailing zeros
 * are hidden and two decimals is the maximum for every currency and magnitude.
 * The currency argument is kept for call-site compatibility.
 */
export function formatAmount(value: number | null | undefined, _currency?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return numberFormatter(0, 2).format(value);
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const decimals = Math.abs(value) < 10 ? 4 : 2;
  return numberFormatter(decimals, decimals).format(value);
}

// Percentages ignore the number-format setting: the decimal point is always
// "." and thousands are separated by an ISO space, so 1 234.5% cannot be
// mistaken for 1.2345%.
const _percentFormatters = new Map<string, Intl.NumberFormat>();

function percentFormatter(min: number, max: number): Intl.NumberFormat {
  const key = `${min}:${max}`;
  let formatter = _percentFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: min,
      maximumFractionDigits: max,
      useGrouping: true,
    });
    _percentFormatters.set(key, formatter);
  }
  return formatter;
}

/**
 * Format a percentage (already multiplied by 100). Precision follows the
 * magnitude, classified on the value rounded to two decimals:
 * under 1 → two fixed decimals (`0.40%`), 1 to 10 → one (`5.0%`),
 * 10 and above → up to two, trailing zeros trimmed (`12%`, `13.15%`).
 */
export function formatPercent(value: number | null | undefined, opts: { sign?: boolean } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const abs = Math.abs(value);
  const rounded = Number(percentFormatter(0, 2).format(abs).replaceAll(',', ''));
  const negative = rounded !== 0 && value < 0;

  let text: string;
  if (rounded < 1) text = percentFormatter(2, 2).format(abs);
  else if (rounded < 10) text = percentFormatter(1, 1).format(abs);
  else text = percentFormatter(0, 2).format(abs);

  const prefix = negative ? '-' : opts.sign && rounded > 0 ? '+' : '';
  return `${prefix}${text.replaceAll(',', ' ')}%`;
}
