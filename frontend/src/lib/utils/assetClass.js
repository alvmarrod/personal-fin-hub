import { t } from '$lib/i18n/index.svelte';

/**
 * Asset classes are stored as free-form strings (`FI`, `VI`, `corp FI`, …).
 * Known values get a localized label; anything custom passes through.
 * `CASH` is injected by the holdings query and `UNSPECIFIED` by the
 * allocation endpoint.
 */
const KEYS = {
  FI: 'assetClass.fi',
  VI: 'assetClass.vi',
  'corp FI': 'assetClass.corpFi',
  'Sovereign FI': 'assetClass.sovereignFi',
  'mix FI': 'assetClass.mixFi',
  REIT: 'assetClass.reit',
  Gold: 'assetClass.gold',
  Monetary: 'assetClass.monetary',
  CASH: 'assetClass.cash',
  UNSPECIFIED: 'assetClass.unclassified',
};

/** @param {string | null | undefined} value */
export function assetClassLabel(value) {
  if (!value) return t('assetClass.unclassified');
  const key = KEYS[value];
  return key ? t(key) : value;
}
