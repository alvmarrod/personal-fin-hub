# World KPIs

> Externally-defined KPIs: their meaning is set outside this project, and their
> values come from a provider (fetched) or from a normalization of a raw series
> (`doc/kpis/world_calc.md`). This is the registry for those rows. Our own KPIs,
> built on top of these, live in `doc/derived/` (§ macro, equity).

Single registry of every world KPI used by the application. It is the source
of truth for KPI definitions. The scoring method lives in
`doc/systems/asset_evaluation/methodology.md`. Pairing and aggregation
configuration lives in `doc/systems/market_cycle/macro_pairings.md`.

Every KPI has one name and one meaning. Consumers refer to a KPI by its name
(treated as a foreign key), never by a re-derived definition.

**Sourcing tags** in the `source` column resolve where each KPI comes from:

| Tag | Meaning | Reference |
|---|---|---|
| `market-api:<Field>` | Retrievable via the External Market API client field list | `doc/datasources/market_api.md` |
| `yfinance:<field>` | Literal `yfinance` field on the yfinance-backed source; exposure against the client field list not yet verified | `doc/datasources/market_api.md` |
| `<derived>` | Computed from retrievable fields; registry row lives in `doc/derived/` | — |
| `<external>` | Not available from `yfinance`; requires a separate source, not built yet | (pipeline pending) |
| `investing-com:<series>` | Economic-calendar series from investing.com | `doc/datasources/macro.md` |
| `ecb:<series>` | Series from the ECB Data Portal JSON API | `doc/datasources/macro.md` |

## 1. Equity World KPIs

Fetched equity KPIs. Their derived counterparts (ratios and trends we compute)
live in `doc/derived/equity.md`.

`kpi_name, kind, section, favorable_direction, source`

| kpi_name | kind | section | favorable_direction | source |
|---|---|---|---|---|
| revenue_growth | level | fundamentals | higher_better | yfinance:revenueGrowth |
| gross_margin | level | fundamentals | higher_better | yfinance:grossMargins |
| operating_margin | level | fundamentals | higher_better | yfinance:operatingMargins |
| roe | level | fundamentals | higher_better | market-api:ROE |
| pe_ratio | level | valuation | lower_better | yfinance:trailingPE |

## 2. Macro World KPIs

`kpi_name, kind, market, favorable_direction, update_frequency, source_note, source`

Macro KPI concepts resolve per market: an `inflation_rate` reading for a
specific country is that KPI's row for that market. Our derived macro KPIs
(trends, `real_interest_rate`, aggregates) live in `doc/derived/macro.md`.

| kpi_name | kind | market | favorable_direction | update_frequency | source_note | source |
|---|---|---|---|---|---|---|
| policy_rate | level | USA | lower_better | event-driven (~8x/yr) | 13-week T-bill yield as proxy | yfinance:^IRX |
| policy_rate | level | Japan | lower_better | event-driven | BOJ policy rate | investing-com:boj-policy-rate |
| policy_rate | level | Spain/Eurozone | lower_better | event-driven | ECB deposit rate | ecb:ecb-deposit-rate |
| yield_curve_slope | level | Japan | higher_better | daily | JGB 10Y minus short-end | \<external\> |
| yield_curve_slope | level | Spain/Eurozone | higher_better | daily | Bund/Bono 10Y minus short-end | \<external\> |
| m2_growth | level | USA | higher_better | monthly (~1mo lag) | USA M2 Money Supply (investing.com); YoY per `doc/kpis/world_calc.md` | investing-com:usa-m2-money-supply |
| m2_growth | level | Japan | higher_better | monthly | Japan M2 money stock, YoY | investing-com:japan-m2-yoy |
| m2_growth | level | Spain/Eurozone | higher_better | monthly | Eurozone M2 (ECB Data Portal, YoY) | ecb:eurozone-m2-yoy |
| inflation_rate | level | USA | neutral | monthly (~1mo lag) | USA CPI YoY | investing-com:usa-cpi-yoy |
| inflation_rate | level | Japan | neutral | monthly (~1mo lag) | Japan CPI YoY | investing-com:japan-cpi-yoy |
| inflation_rate | level | Spain/Eurozone | neutral | monthly (~1mo lag) | Eurozone HICP (Eurostat; listed as "CPI YoY" on investing.com) | investing-com:eurozone-cpi-yoy |

`favorable_direction = neutral` marks KPIs that feed market-cycle state
detection rather than asset-evaluation favorability.

## 3. Data Availability & Limitations

- `yield_curve_slope` (Japan, Spain/Eurozone) and the remaining Spain/Eurozone
  macro readings are `<external>` today; committed to building a separate
  source for all of them rather than dropping any.
- `inflation_rate` (all markets), `policy_rate` (Japan, Spain/Eurozone), and
  `m2_growth` (USA, Japan, Spain/Eurozone) were `<external>` and are now
  sourced from investing.com's economic calendar and the ECB Data Portal
  (`investing-com:` / `ecb:` rows), per `doc/datasources/macro.md`.
- yfinance typically exposes ~4 years of annual fundamentals — the 5y trend
  default from the parent HLD will run on a shorter available window until
  deeper history is sourced elsewhere.
- `info` dict fields (`trailingPE`, `returnOnEquity`, etc.) vary in
  reliability and coverage across tickers, and especially across non-US
  exchanges — an implementation-time risk this document doesn't resolve.
- The External Market API client documents a fixed field list; only `ROE`
  among the equity KPIs maps to it today. `yfinance:`-tagged fields are
  assumed to be served by the yfinance-backed source and must be verified
  against the client during implementation.
