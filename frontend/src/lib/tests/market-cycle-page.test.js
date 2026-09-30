import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/investment-market-cycle/+page.svelte';

const { analyticsMock, SCOPES } = vi.hoisted(() => ({
  analyticsMock: { investmentMarketCycle: vi.fn() },
  SCOPES: [
    { key: 'global', labelKey: 'marketCycle.scope.world', ready: false },
    { key: 'usa', labelKey: 'marketCycle.scope.usa', ready: true },
    { key: 'japan', labelKey: 'marketCycle.scope.japan', ready: false },
    { key: 'spain-eurozone', labelKey: 'marketCycle.scope.spainEurozone', ready: true },
  ],
}));

vi.mock('$lib/api/analytics.js', () => ({
  analytics: analyticsMock,
  MARKET_CYCLE_SCOPES: SCOPES,
}));

vi.mock('$lib/api/client.js', () => ({ api: { get: vi.fn(() => Promise.resolve({})) } }));

const realRateFormula = {
  code: 'real_rate',
  inputs: [
    { kpi: 'policy_rate', value: 5.0 },
    { kpi: 'inflation_rate', value: 3.0 },
  ],
  result: 2.0,
};

const status = {
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
          code: 'real_rates_high',
          metric: 'real_interest_rate',
          kind: 'threshold',
          met: false,
          value: 2.0,
          unit: '%',
          condition: { op: '>', target: 3.0 },
          formula: realRateFormula,
        },
      ],
    },
  ],
  entry_signals: 'favourable',
  ambiguous_confirmation: false,
  last_update: '2026-09-25T10:00:00Z',
  metrics: [
    { kpi: 'inflation_rate', kind: 'level', value: 3.0, unit: '%', prev_value: 2.9, delta: 0.1, formula: null },
    { kpi: 'policy_rate', kind: 'level', value: 5.0, unit: '%', prev_value: 5.0, delta: 0.0, formula: null },
    {
      kpi: 'real_interest_rate',
      kind: 'level',
      value: 2.0,
      unit: '%',
      prev_value: 2.1,
      delta: -0.1,
      formula: realRateFormula,
    },
  ],
};

describe('Investment Market Cycle page', () => {
  beforeEach(() => {
    setLocale('en-US');
    analyticsMock.investmentMarketCycle.mockReset();
  });

  afterEach(cleanup);

  it('loads the default scope and renders the status', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue(status);
    const { container } = render(Page);

    await waitFor(() => expect(analyticsMock.investmentMarketCycle).toHaveBeenCalledWith('spain-eurozone'));
    expect(await screen.findByText('Investment Market Cycle')).toBeTruthy();
    expect(await screen.findByText('Favourable entry')).toBeTruthy();
    expect(container.querySelector('svg.state-diagram')).toBeTruthy();
    expect(container.querySelector('.node.active')).toBeTruthy();
    expect(container.querySelector('.panel-approaching').textContent).toContain('Approaching transition');
    expect(container.querySelector('.edge-active')).toBeTruthy();
  });

  it('shows a warning and empty state when the scope has no data (400)', async () => {
    analyticsMock.investmentMarketCycle.mockRejectedValue(Object.assign(new Error('no data'), { status: 400 }));
    render(Page);

    expect(await screen.findByText('Missing data sources')).toBeTruthy();
    expect(await screen.findByText('No data for this scope yet')).toBeTruthy();
  });

  it('shows an error card on a non-400 failure', async () => {
    analyticsMock.investmentMarketCycle.mockRejectedValue(Object.assign(new Error('boom'), { status: 500 }));
    render(Page);

    expect(await screen.findByText('boom')).toBeTruthy();
  });

  it('refetches when the scope changes', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue(status);
    const { container } = render(Page);
    await waitFor(() => expect(analyticsMock.investmentMarketCycle).toHaveBeenCalledWith('spain-eurozone'));

    const select = container.querySelector('select');
    await fireEvent.change(select, { target: { value: 'usa' } });
    await waitFor(() => expect(analyticsMock.investmentMarketCycle).toHaveBeenCalledWith('usa'));
  });

  it('renders not-ready scopes as disabled options', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue(status);
    const { container } = render(Page);
    await waitFor(() => expect(analyticsMock.investmentMarketCycle).toHaveBeenCalled());

    const japan = container.querySelector('option[value="japan"]');
    const world = container.querySelector('option[value="global"]');
    expect(japan.disabled).toBe(true);
    expect(world.disabled).toBe(true);
  });

  it('renders the ambiguous chip when confirmation is ambiguous', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue({ ...status, ambiguous_confirmation: true });
    render(Page);
    expect(await screen.findByText('transition analysis paused')).toBeTruthy();
  });

  it('renders the strong entry signal', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue({
      ...status,
      current_state: { id: 5, name: 'First Rate Cut' },
      entry_signals: 'strong',
    });
    const { container } = render(Page);
    await waitFor(() => expect(analyticsMock.investmentMarketCycle).toHaveBeenCalled());
    await waitFor(() => expect(container.querySelector('.supporting-panel').textContent).toContain('Strong entry signal'));
  });

  it('renders the key metrics table', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue(status);
    const { container } = render(Page);
    await waitFor(() => expect(container.querySelector('.metrics-panel')).toBeTruthy());
    const text = container.querySelector('.metrics-panel').textContent;
    expect(text).toContain('Inflation rate');
    expect(text).toContain('Nominal policy rate');
    expect(text).toContain('Real interest rate');
    expect(text).toContain('5.00%');
  });

  it('renders each transition signal with its value, threshold, and progress', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue(status);
    const { container } = render(Page);
    await waitFor(() => expect(container.querySelector('.signals-panel')).toBeTruthy());
    const text = container.querySelector('.signals-panel').textContent;
    expect(text).toContain('Real interest rate');
    expect(text).toContain('5.00%'); // formula input: policy rate
    expect(text).toContain('3.00%'); // formula input: inflation rate
    expect(text).toContain('above 3.00%'); // threshold
    expect(text).toContain('not met');
    expect(text).toContain('3 of 3 months held');
  });

  it('collapses non-approaching transitions', async () => {
    analyticsMock.investmentMarketCycle.mockResolvedValue({
      ...status,
      active_transitions: [
        status.active_transitions[0],
        {
          source: 'High Real Rates',
          target: 'Hiking Cycle',
          status: 'Inactive',
          direction: 'Reverse',
          priority: 8,
          held_months: 0,
          required_months: 3,
          signals: [],
        },
      ],
    });
    const { container } = render(Page);
    await waitFor(() => expect(container.querySelector('.signals-panel')).toBeTruthy());
    const details = container.querySelectorAll('.signals-panel details');
    expect(details.length).toBe(1);
    expect(container.querySelectorAll('.transition.approaching').length).toBe(1);
  });
});
