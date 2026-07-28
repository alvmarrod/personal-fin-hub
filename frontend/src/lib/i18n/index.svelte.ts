import en from './locales/en';
import es from './locales/es';

type LocaleCode = string;
type Translations = Record<string, string>;

const dictionaries: Record<LocaleCode, Translations> = {
  'en-US': en,
  'es-ES': es,
};

let _locale: LocaleCode = $state('en-US');

export function t(key: string, params?: Record<string, string | number>): string {
  const dict = dictionaries[_locale];
  let value = dict?.[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      value = value.replaceAll(`{${k}}`, String(v));
    }
  }
  return value;
}

export function locale(): LocaleCode {
  return _locale;
}

export function setLocale(code: LocaleCode): void {
  if (dictionaries[code]) {
    _locale = code;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('locale', code);
    }
  }
}

export function initLocale(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem('locale');
  if (saved && dictionaries[saved]) {
    _locale = saved;
  }
}

export const localeOptions = [
  { code: 'en-US', label: 'English' },
  { code: 'es-ES', label: 'Español' },
] as const;

export function isLocale(code: LocaleCode): boolean {
  return code in dictionaries;
}
