import { describe, it, expect } from 'vitest';
import { currencyExposure } from '$lib/utils/exposure.js';

describe('currencyExposure', () => {
  it('groups converted values by native currency, largest first', () => {
    const result = currencyExposure([
      { origCurrency: 'EUR', unifiedAmount: 1000, rateMissing: false },
      { origCurrency: 'USD', unifiedAmount: 500, rateMissing: false },
      { origCurrency: 'EUR', unifiedAmount: 250, rateMissing: false },
    ]);

    expect(result.labels).toEqual(['EUR', 'USD']);
    expect(result.values).toEqual([1250, 500]);
    expect(result.excluded).toBe(0);
  });

  it('excludes rows without a conversion and counts them', () => {
    const result = currencyExposure([
      { origCurrency: 'EUR', unifiedAmount: 1000, rateMissing: false },
      { origCurrency: 'JPY', unifiedAmount: 9000000, rateMissing: true },
    ]);

    expect(result.labels).toEqual(['EUR']);
    expect(result.values).toEqual([1000]);
    expect(result.excluded).toBe(1);
  });

  it('falls back to a placeholder for a missing currency code', () => {
    const result = currencyExposure([{ origCurrency: null, unifiedAmount: 10 }]);
    expect(result.labels).toEqual(['—']);
  });

  it('returns empty lists when everything was excluded', () => {
    const result = currencyExposure([{ origCurrency: 'JPY', unifiedAmount: 1, rateMissing: true }]);
    expect(result.labels).toEqual([]);
    expect(result.values).toEqual([]);
    expect(result.excluded).toBe(1);
  });

  it('handles no rows', () => {
    expect(currencyExposure([])).toEqual({ labels: [], values: [], excluded: 0 });
  });
});
