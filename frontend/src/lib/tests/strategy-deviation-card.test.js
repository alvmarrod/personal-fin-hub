import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import StrategyDeviationCard from '../components/StrategyDeviationCard.svelte';

const DRIFT = {
  effective_from: '2026-01-01',
  as_of: '2026-11-21',
  total: 30700,
  rate_missing: false,
  buckets: [
    { bucket: 'equities', target_pct: 55, value: 19034, share_pct: 62, drift_pp: 7, amount_to_move: -2149, rate_missing: false },
    { bucket: 'bonds', target_pct: 30, value: 7368, share_pct: 24, drift_pp: -6, amount_to_move: 1842, rate_missing: false },
    { bucket: 'cash', target_pct: 15, value: 3070, share_pct: 10, drift_pp: -5, amount_to_move: 1535, rate_missing: false },
    { bucket: 'real_estate', target_pct: 0, value: 0, share_pct: 0, drift_pp: 0, amount_to_move: 0, rate_missing: false },
    { bucket: 'gold', target_pct: 0, value: 0, share_pct: 0, drift_pp: 0, amount_to_move: 0, rate_missing: false },
  ],
  unassigned: { value: 0, share_pct: 0, rate_missing: false },
};

describe('StrategyDeviationCard', () => {
  beforeEach(() => {
    setLocale('en-US');
  });

  afterEach(cleanup);

  it('draws the bubble chart when a target is effective', () => {
    const { container } = render(StrategyDeviationCard, { props: { drift: DRIFT } });

    expect(container.querySelector('canvas')).toBeTruthy();
    expect(screen.getByText('2 bucket(s) at 0% on target.')).toBeTruthy();
  });

  it('shows the call to action when no target is effective', () => {
    const { container } = render(StrategyDeviationCard, {
      props: { drift: { ...DRIFT, effective_from: null, buckets: [] } },
    });

    expect(container.querySelector('canvas')).toBeNull();
    expect(screen.getByText('Go to strategy view')).toBeTruthy();
  });

  it('shows the call to action without a drift payload', () => {
    render(StrategyDeviationCard, { props: { drift: null } });
    expect(screen.getByText('Go to strategy view')).toBeTruthy();
  });
});
