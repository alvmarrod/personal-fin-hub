# Derived Macro KPIs

> Macro KPIs that are computed from other KPIs (our constructions), as opposed
> to world KPIs, which are externally defined and fetched or normalized
> (`doc/kpis/world.md`, `doc/kpis/world_calc.md`). This document holds both the
> registry rows and the mathematics for these derived KPIs.

## Registry

`kpi_name, kind, market, favorable_direction, update_frequency, source_note, source`

These row's values come from the computations in this document (tagged
`<derived>`); their inputs are the world KPIs in `doc/kpis/world.md`.

| kpi_name | kind | market | favorable_direction | update_frequency | source_note | source |
|---|---|---|---|---|---|---|
| policy_rate_trend | trend | USA | lower_better | event-driven | direction of the above | \<derived\> |
| policy_rate_trend | trend | Japan | lower_better | event-driven | direction of the above | \<derived\> |
| policy_rate_trend | trend | Spain/Eurozone | lower_better | event-driven | direction of the above | \<derived\> |
| yield_curve_slope | level | USA | higher_better | daily | 10Y (^TNX) minus 3M (^IRX) | \<derived\> |
| yield_curve_slope_trend | trend | USA | higher_better | daily | slope of the above | \<derived\> |
| yield_curve_slope | level | Japan | higher_better | daily | JGB 10Y minus short-end | \<external\> |
| yield_curve_slope_trend | trend | Japan | higher_better | daily | slope of the above | \<derived\> |
| yield_curve_slope | level | Spain/Eurozone | higher_better | daily | Bund/Bono 10Y minus short-end | \<external\> |
| yield_curve_slope_trend | trend | Spain/Eurozone | higher_better | daily | slope of the above | \<derived\> |
| m2_growth_trend | trend | USA | higher_better | monthly | slope of the above | \<derived\> |
| m2_growth_trend | trend | Japan | higher_better | monthly | slope of the above | \<derived\> |
| m2_growth_trend | trend | Spain/Eurozone | higher_better | monthly | slope of the above | \<derived\> |
| policy_rate / yield_curve_slope / m2_growth (+ trends) | level & trend | Global aggregate | (same as above) | (same as above) | weighted blend of USA/Japan/Spain readings | \<derived\> (m2_growth inputs all sourced; curve inputs USA-only until Japan/Spain curve sources exist) |
| inflation_rate | level | Global aggregate | neutral | monthly (~1mo lag) | weighted blend of the above | \<derived\> (currently USA/Spain-Eurozone-only until Japan CPI exists) |
| inflation_rate_trend | trend | USA | neutral | monthly | direction of inflation_rate | \<derived\> |
| inflation_rate_trend | trend | Japan | neutral | monthly | direction of inflation_rate | \<derived\> |
| inflation_rate_trend | trend | Spain/Eurozone | neutral | monthly | direction of inflation_rate | \<derived\> |
| inflation_rate_trend | trend | Global aggregate | neutral | monthly | direction of inflation_rate | \<derived\> |
| real_interest_rate | level | USA | neutral | event-driven | policy_rate − inflation_rate | \<derived\> |
| real_interest_rate | level | Japan | neutral | event-driven | policy_rate − inflation_rate | \<derived\> |
| real_interest_rate | level | Spain/Eurozone | neutral | event-driven | policy_rate − inflation_rate | \<derived\> |
| real_interest_rate | level | Global aggregate | neutral | event-driven | policy_rate − inflation_rate | \<derived\> |
| real_interest_rate_trend | trend | USA | neutral | event-driven | direction of real_interest_rate | \<derived\> |
| real_interest_rate_trend | trend | Japan | neutral | event-driven | direction of real_interest_rate | \<derived\> |
| real_interest_rate_trend | trend | Spain/Eurozone | neutral | event-driven | direction of real_interest_rate | \<derived\> |
| real_interest_rate_trend | trend | Global aggregate | neutral | event-driven | direction of real_interest_rate | \<derived\> |

`policy_rate` and `policy_rate_trend` are the nominal policy rate and the
nominal rate trend required by the Investment Market Cycle (HLD §10).

The `<derived>` market-cycle rows are computed below:

- `inflation_rate_trend` and `real_interest_rate_trend`: trend direction.
- `real_interest_rate`: nominal policy rate minus inflation.
- `yield_curve_slope` (USA): `yield_10y` minus `policy_rate` (both via the
  External Market API — `^TNX − ^IRX`); `yield_curve_slope_trend` is its
  trend direction.

### Deferred

These registry rows are defined but **not yet computed** — their inputs are not
sourced (no availability model; they become computable when a source is added):

- `yield_curve_slope` (Japan, Spain/Eurozone) and their trends: the curve legs
  are `<external>` (the USA leg is now sourced, `^TNX − ^IRX`).
- The **Global aggregate** rows (`policy_rate`, `m2_growth`,
  `yield_curve_slope`, their trends, and `inflation_rate`): the aggregate
  weighting needs per-country legs (e.g. France/Germany/Italy) that are not
  sourced; multiple market legs are also missing.

Implementation: `backend/services/derived_kpi_calc.py` (mathematics) and
`backend/services/derived_kpi_svc.py` (registry + access). Computed on demand
from the world KPIs; nothing is persisted.

## Trend direction

A trend KPI reduces a level series to a direction. Direction values are
`increasing`, `stable`, and `decreasing` (HLD §3).

The trend is the **immediate slope**: for each point, the direction of the
change from the previous point — not a regression, CAGR, or percent change over
a window.

```text
Δ = value(t) - value(t-1)
|Δ| <= deadband  -> stable
Δ >  deadband    -> increasing
Δ < -deadband    -> decreasing
```

- The deadband is a configurable parameter (`derived.trend_deadband`, default
  `0.0`): any real change is a direction, but a comparison floor guards against
  float representation noise (a value that only differs in the last bits is
  `stable`).
- The first point of a series has no predecessor and produces no direction.
- **Resolution.** Computed on a monthly grid. A monthly series is used as-is;
  an event/step series (policy rates) is forward-filled to **month-end** first
  — a month takes the rate in effect on its last day, so a mid-month change
  lands in that month, and the current month takes the latest known value.
- The *run/reversal* signal the immediate slope enables — several consecutive
  down-slopes then a rise, i.e. a pause or reversal in a hiking/cutting phase —
  is **not** this KPI. It belongs to the state engine's signals
  (`hikes_stopped`, `cuts_stopped`, `hikes_resumed`, `first_cut_detected`;
  `doc/systems/market_cycle/state_engine.md` §4).

Catalog rows with `kind = trend` (`policy_rate_trend`,
`inflation_rate_trend`, `real_interest_rate_trend`, and the equity `_trend_5y`
rows) take their value from this section.

## Real interest rate

```text
real_rate = nominal_policy_rate - inflation_rate
```

Both terms are percentages for the same market. The nominal policy rate is
the `policy_rate` KPI; inflation is the `inflation_rate` KPI (see
`doc/kpis/world.md`). The real interest rate is a separate metric from the
nominal policy rate: a high nominal rate does not imply high real rates, and a
low nominal rate does not imply low real rates (HLD §3, §13).

## Related

- Persistence and confirmation, and the state-identification inputs consumed by
  the cycle engine, live in the state-engine contract:
  `doc/systems/market_cycle/state_engine.md` (§5, §7).
- World KPI definitions and sourcing: `doc/kpis/world.md`,
  `doc/datasources/macro.md`.
- Equity derived KPIs: `doc/derived/equity.md`.
