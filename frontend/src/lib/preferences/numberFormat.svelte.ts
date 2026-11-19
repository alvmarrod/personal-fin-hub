/**
 * Thousands and decimal separators for every number the app formats.
 * Independent of the language locale: the choice is the user's.
 *
 * 'comma-dot' = 1,234.56, 'dot-comma' = 1.234,56 (default).
 */
export type NumberFormat = 'comma-dot' | 'dot-comma';

export const NUMBER_FORMATS: NumberFormat[] = ['comma-dot', 'dot-comma'];

const STORAGE_KEY = 'numberFormat';

let _numberFormat: NumberFormat = $state('dot-comma');

export function numberFormat(): NumberFormat {
  return _numberFormat;
}

export function setNumberFormat(value: string): void {
  if (!NUMBER_FORMATS.includes(value as NumberFormat)) return;
  _numberFormat = value as NumberFormat;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, value);
  }
}

export function initNumberFormat(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && NUMBER_FORMATS.includes(saved as NumberFormat)) {
    _numberFormat = saved as NumberFormat;
  }
}
