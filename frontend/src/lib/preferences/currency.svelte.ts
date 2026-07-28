const CURRENCY_SYMBOLS = {
  USD: '$',
  EUR: '€',
  JPY: '¥',
  GBP: '£',
  CHF: 'CHF ',
  CAD: 'C$',
  AUD: 'A$',
  CNY: '¥',
  HKD: 'HK$',
  SGD: 'S$',
  KRW: '₩',
  INR: '₹',
  BRL: 'R$',
  MXN: 'MX$',
  SEK: 'kr',
  NOK: 'kr',
  DKK: 'kr',
  PLN: 'zł',
  TRY: '₺',
  RUB: '₽',
  ZAR: 'R ',
};

let _currency: string = $state('EUR');

export function displayCurrency(): string {
  return _currency;
}

export function setDisplayCurrency(code: string): void {
  _currency = code;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('displayCurrency', code);
  }
}

export function initCurrency(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem('displayCurrency');
  if (saved) {
    _currency = saved;
  }
}

export function currencySymbol(): string {
  return CURRENCY_SYMBOLS[_currency] ?? _currency + ' ';
}

export function getSymbolFor(currencyCode: string): string {
  return CURRENCY_SYMBOLS[currencyCode] ?? currencyCode + ' ';
}
