// Mock engine status for the Investment Market Cycle tutorial (state_engine.md §9).
// Shape must match the endpoint: each transition carries its signals and
// progress, and the status carries the six key metrics.
const realRate = {
  code: 'real_rate',
  inputs: [
    { kpi: 'policy_rate', value: 5.0 },
    { kpi: 'inflation_rate', value: 3.0 },
  ],
  result: 2.0,
};

const marketCycleStatus = {
  scope: 'spain-eurozone',
  current_state: { id: 4, name: 'High Real Rates' },
  current_state_since: '2026-01-15',
  active_transitions: [
    {
      source: 'High Real Rates',
      target: 'First Rate Cut',
      status: 'Triggered',
      direction: 'Forward',
      priority: 4,
      held_months: 3,
      required_months: 3,
      signals: [
        {
          code: 'first_cut_detected',
          metric: 'policy_rate_trend',
          kind: 'combination',
          met: true,
          value: null,
          unit: null,
          condition: null,
          formula: null,
          parts: [
            {
              metric: 'policy_rate_trend',
              kind: 'direction',
              met: true,
              value: 'decreasing',
              unit: null,
              condition: { op: '==', target: 'decreasing' },
              formula: {
                code: 'slope_step',
                inputs: [{ kpi: 'policy_rate', value: 5.0, prev_value: 5.25 }],
                delta: -0.25,
              },
            },
            {
              metric: 'state',
              kind: 'state',
              met: true,
              value: 'High Real Rates',
              unit: null,
              condition: { op: 'in', target: ['Hiking Cycle', 'High Real Rates'] },
              formula: null,
            },
          ],
        },
      ],
    },
    {
      source: 'High Real Rates',
      target: 'Hiking Cycle',
      status: 'Inactive',
      direction: 'Reverse',
      priority: 8,
      held_months: 0,
      required_months: 3,
      signals: [
        {
          code: 'hikes_resumed',
          metric: 'policy_rate_trend',
          kind: 'combination',
          met: false,
          value: null,
          unit: null,
          condition: null,
          formula: null,
          parts: [
            {
              metric: 'policy_rate_trend',
              kind: 'direction',
              met: false,
              value: 'decreasing',
              unit: null,
              condition: { op: '==', target: 'increasing' },
              formula: {
                code: 'slope_step',
                inputs: [{ kpi: 'policy_rate', value: 5.0, prev_value: 5.25 }],
                delta: -0.25,
              },
            },
            {
              metric: 'policy_rate_trend',
              kind: 'history',
              met: true,
              value: null,
              unit: null,
              condition: { op: 'none_within', target: 'increasing', window: 6 },
              formula: null,
            },
          ],
        },
        {
          code: 'real_rates_climbing',
          metric: 'real_interest_rate_trend',
          kind: 'direction',
          met: false,
          value: 'decreasing',
          unit: null,
          condition: { op: '==', target: 'increasing' },
          formula: {
            code: 'slope_step',
            inputs: [{ kpi: 'real_interest_rate', value: 2.0, prev_value: 2.05 }],
            delta: -0.05,
          },
        },
      ],
    },
  ],
  entry_signals: 'favourable',
  ambiguous_confirmation: false,
  last_update: '2026-09-25T10:00:00Z',
  metrics: [
    { kpi: 'inflation_rate', kind: 'level', value: 3.0, unit: '%', prev_value: 3.2, delta: -0.2, formula: null },
    {
      kpi: 'inflation_rate_trend',
      kind: 'direction',
      value: 'decreasing',
      unit: null,
      prev_value: null,
      delta: null,
      formula: { code: 'slope_step', inputs: [{ kpi: 'inflation_rate', value: 3.0, prev_value: 3.2 }], delta: -0.2 },
    },
    { kpi: 'policy_rate', kind: 'level', value: 5.0, unit: '%', prev_value: 5.25, delta: -0.25, formula: null },
    {
      kpi: 'policy_rate_trend',
      kind: 'direction',
      value: 'decreasing',
      unit: null,
      prev_value: null,
      delta: null,
      formula: { code: 'slope_step', inputs: [{ kpi: 'policy_rate', value: 5.0, prev_value: 5.25 }], delta: -0.25 },
    },
    { kpi: 'real_interest_rate', kind: 'level', value: 2.0, unit: '%', prev_value: 2.05, delta: -0.05, formula: realRate },
    {
      kpi: 'real_interest_rate_trend',
      kind: 'direction',
      value: 'decreasing',
      unit: null,
      prev_value: null,
      delta: null,
      formula: {
        code: 'slope_step',
        inputs: [{ kpi: 'real_interest_rate', value: 2.0, prev_value: 2.05 }],
        delta: -0.05,
      },
    },
  ],
};

const marketCycleMock = {
  '/analytics/investment-market-cycle': marketCycleStatus,
};

export default marketCycleMock;
