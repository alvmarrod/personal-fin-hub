/**
 * Currency exposure from the dashboard's grouped holding rows.
 *
 * Rows whose currency could not be converted are excluded: their
 * `unifiedAmount` is really the native value, so including them would
 * distort the shares. The caller shows the count.
 *
 * @param {Array<{ origCurrency?: string | null, origAmount?: number, unifiedAmount?: number, rateMissing?: boolean }>} rows
 * @returns {{ labels: string[], values: number[], original: number[], excluded: number }}
 */
export function currencyExposure(rows) {
  const converted = new Map();
  const original = new Map();
  let excluded = 0;

  for (const row of rows) {
    if (row.rateMissing) {
      excluded += 1;
      continue;
    }
    const code = row.origCurrency || '—';
    converted.set(code, (converted.get(code) || 0) + (row.unifiedAmount || 0));
    original.set(code, (original.get(code) || 0) + (row.origAmount || 0));
  }

  const sorted = [...converted.entries()].sort((a, b) => b[1] - a[1]);
  return {
    labels: sorted.map(([code]) => code),
    values: sorted.map(([, value]) => value),
    original: sorted.map(([code]) => original.get(code) || 0),
    excluded,
  };
}
