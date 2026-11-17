/**
 * Display order for calendar dates. Independent of the language locale: the
 * choice is the user's, not the dictionary's.
 *
 * 'dmy' = DD/MM/YYYY (default), 'mdy' = MM/DD/YYYY, 'iso' = YYYY-MM-DD.
 */
export type DateFormat = 'dmy' | 'mdy' | 'iso';

export const DATE_FORMATS: DateFormat[] = ['dmy', 'mdy', 'iso'];

const STORAGE_KEY = 'dateFormat';

let _dateFormat: DateFormat = $state('dmy');

export function dateFormat(): DateFormat {
  return _dateFormat;
}

export function setDateFormat(value: DateFormat): void {
  if (!DATE_FORMATS.includes(value)) return;
  _dateFormat = value;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, value);
  }
}

export function initDateFormat(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && DATE_FORMATS.includes(saved as DateFormat)) {
    _dateFormat = saved as DateFormat;
  }
}
