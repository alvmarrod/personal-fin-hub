const marketCycleStatus = {
  scope: 'spain-eurozone',
  current_state: { id: 4, name: 'High Real Rates' },
  current_state_since: '2026-01-15',
  active_transitions: [
    { source: 'High Real Rates', target: 'First Rate Cut', status: 'Triggered', direction: 'Forward', priority: 4 },
  ],
  entry_signals: 'favourable',
  ambiguous_confirmation: false,
  last_update: '2026-09-25T10:00:00Z',
};

const marketCycleMock = {
  '/analytics/investment-market-cycle': marketCycleStatus,
};

export default marketCycleMock;
