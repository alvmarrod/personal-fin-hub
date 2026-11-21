const strategyMock = {
  '/strategy': [
    {
      effective_from: '2026-01-01',
      targets: { equities: 55, bonds: 30, cash: 15, real_estate: 0, gold: 0 },
      updated_at: '2026-01-01 10:00:00',
    },
    {
      effective_from: '2027-01-01',
      targets: { equities: 53, bonds: 32, cash: 15, real_estate: 0, gold: 0 },
      updated_at: '2026-11-01 10:00:00',
    },
  ],
  '/strategy/drift': {
    effective_from: '2026-01-01',
    as_of: '2026-11-21',
    total: 30700,
    rate_missing: false,
    buckets: [
      { bucket: 'equities', target_pct: 55, value: 19034, share_pct: 62.0, drift_pp: 7.0, amount_to_move: -2149, rate_missing: false },
      { bucket: 'bonds', target_pct: 30, value: 7368, share_pct: 24.0, drift_pp: -6.0, amount_to_move: 1842, rate_missing: false },
      { bucket: 'cash', target_pct: 15, value: 3070, share_pct: 10.0, drift_pp: -5.0, amount_to_move: 1535, rate_missing: false },
      { bucket: 'real_estate', target_pct: 0, value: 0, share_pct: 0.0, drift_pp: 0.0, amount_to_move: 0, rate_missing: false },
      { bucket: 'gold', target_pct: 0, value: 0, share_pct: 0.0, drift_pp: 0.0, amount_to_move: 0, rate_missing: false },
    ],
    unassigned: { value: 1228, share_pct: 4.0, rate_missing: false },
  },
};

export default strategyMock;
