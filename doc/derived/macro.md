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

## Trend direction

A trend KPI reduces a level series to a direction. Direction values are
`increasing`, `stable`, and `decreasing` (HLD §3).

1. Compute the slope of the level KPI over the lookback window. The slope
   method follows the trend definition in
   `doc/systems/asset_evaluation/methodology.md` §4.2. Default lookback is
   5 years; a shorter available window is flagged low-confidence rather than
   excluded.
2. Map the slope to a direction with a deadband:

```text
|slope| <= deadband   -> stable
slope > deadband      -> increasing
slope < -deadband     -> decreasing
```

1. The lookback window, the slope method, and the deadband are configurable
   parameters, not constants.

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
