# KPI Catalog

Single registry of every equity and macro KPI used by the application. It is
the source of truth for KPI definitions. The scoring method lives in
`doc/subsystems/asset_evaluation_methodology.md`. Pairing and aggregation
configuration lives in `doc/subsystems/macro_pairings.md`. No implementation
code.

Every KPI has one name and one meaning. Consumers refer to a KPI by its name
(treated as a foreign key), never by a re-derived definition.

**Sourcing tags** in the `source` column resolve where each KPI comes from:

| Tag | Meaning | Reference |
|---|---|---|
| `market-api:<Field>` | Retrievable via the External Market API client field list | `doc/subsystems/market_api_client.md` |
| `yfinance:<field>` | Literal `yfinance` field on the yfinance-backed source; exposure against the client field list not yet verified | `doc/subsystems/market_api_client.md` |
| `<derived>` | Computed from retrievable fields; formula in the derivation notes below or in `doc/calculations.md` | — |
| `<external>` | Not available from `yfinance`; requires a separate source, not built yet | (pipeline pending) |

## 1. Equity KPI Table

`kpi_name, kind, section, favorable_direction, source`

| kpi_name | kind | section | favorable_direction | source |
|---|---|---|---|---|
| revenue_growth | level | fundamentals | higher_better | yfinance:revenueGrowth |
| revenue_growth_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| gross_margin | level | fundamentals | higher_better | yfinance:grossMargins |
| gross_margin_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| operating_margin | level | fundamentals | higher_better | yfinance:operatingMargins |
| operating_margin_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| roe | level | fundamentals | higher_better | market-api:ROE |
| roe_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| roic | level | fundamentals | higher_better | \<derived\> |
| roic_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| net_debt_to_equity | level | fundamentals | lower_better | \<derived\> |
| net_debt_to_equity_trend_5y | trend | fundamentals | lower_better | \<derived\> |
| interest_coverage_ebit | level | fundamentals | higher_better | \<derived\> |
| interest_coverage_ebit_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| fcf_conversion | level | fundamentals | higher_better | \<derived\> |
| fcf_conversion_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| pe_ratio | level | valuation | lower_better | yfinance:trailingPE |
| pe_ratio_trend_5y | trend | valuation | lower_better | \<derived\> |
| ev_ebit | level | valuation | lower_better | \<derived\> |
| ev_ebit_trend_5y | trend | valuation | lower_better | \<derived\> |
| p_fcf | level | valuation | lower_better | \<derived\> |
| p_fcf_trend_5y | trend | valuation | lower_better | \<derived\> |
| shareholder_yield | level | valuation | higher_better | \<derived\> |
| shareholder_yield_trend_5y | trend | valuation | higher_better | \<derived\> |

Derivation notes for `<derived>` level KPIs:

- `roic`: NOPAT / invested capital, from `.financials` + `.balance_sheet`.
- `net_debt_to_equity`: (`totalDebt` − `totalCash`) / stockholders' equity.
- `interest_coverage_ebit`: operating income / interest expense, from `.financials`.
- `fcf_conversion`: `freeCashflow` / net income (`netIncomeToCommon`).
- `ev_ebit`: `enterpriseValue` / operating income.
- `p_fcf`: `marketCap` / `freeCashflow`.
- `shareholder_yield`: `dividendYield` + buyback yield (from trailing
  change in `sharesOutstanding`).
- All `_trend_5y` rows: slope of the level metric's own history. yfinance
  typically exposes ~4 years of annual statements via `.financials` /
  `.balance_sheet` / `.cashflow` — trend direction semantics in
  `doc/calculations.md` §18.1.

## 2. Macro KPI Table

`kpi_name, kind, market, favorable_direction, update_frequency, source_note, source`

Macro KPI concepts resolve per market: an `inflation_rate` reading for a
specific country is that KPI's row for that market. `favorable_direction =
neutral` marks KPIs that feed market-cycle state detection rather than
asset-evaluation favorability.

| kpi_name | kind | market | favorable_direction | update_frequency | source_note | source |
|---|---|---|---|---|---|---|
| policy_rate | level | USA | lower_better | event-driven (~8x/yr) | 13-week T-bill yield as proxy | yfinance:^IRX |
| policy_rate_trend | trend | USA | lower_better | event-driven | direction of the above | \<derived\> |
| policy_rate | level | Japan | lower_better | event-driven | BOJ policy rate | \<external\> |
| policy_rate_trend | trend | Japan | lower_better | event-driven | direction of the above | \<derived\> |
| policy_rate | level | Spain/Eurozone | lower_better | event-driven | ECB deposit rate | \<external\> |
| policy_rate_trend | trend | Spain/Eurozone | lower_better | event-driven | direction of the above | \<derived\> |
| yield_curve_slope | level | USA | higher_better | daily | 10Y (^TNX) minus 3M (^IRX) | \<derived\> |
| yield_curve_slope_trend | trend | USA | higher_better | daily | slope of the above | \<derived\> |
| yield_curve_slope | level | Japan | higher_better | daily | JGB 10Y minus short-end | \<external\> |
| yield_curve_slope_trend | trend | Japan | higher_better | daily | slope of the above | \<derived\> |
| yield_curve_slope | level | Spain/Eurozone | higher_better | daily | Bund/Bono 10Y minus short-end | \<external\> |
| yield_curve_slope_trend | trend | Spain/Eurozone | higher_better | daily | slope of the above | \<derived\> |
| m2_growth | level | USA | higher_better | monthly (~1mo lag) | FRED M2SL, YoY % | \<external\> |
| m2_growth_trend | trend | USA | higher_better | monthly | slope of the above | \<derived\> |
| m2_growth | level | Japan | higher_better | monthly | BOJ money stock stats | \<external\> |
| m2_growth_trend | trend | Japan | higher_better | monthly | slope of the above | \<derived\> |
| m2_growth | level | Spain/Eurozone | higher_better | monthly | ECB money supply stats | \<external\> |
| m2_growth_trend | trend | Spain/Eurozone | higher_better | monthly | slope of the above | \<derived\> |
| policy_rate / yield_curve_slope / m2_growth (+ trends) | level & trend | Global aggregate | (same as above) | (same as above) | weighted blend of USA/Japan/Spain readings | \<derived\> (currently USA-only until Japan/Spain sources exist) |

Market-cycle KPIs. Required by the Investment Market Cycle state engine
(`doc/plans/Investment_Market_Cycle_HLD_And_View.md` §10, §13):

| kpi_name | kind | market | favorable_direction | update_frequency | source_note | source |
|---|---|---|---|---|---|---|
| inflation_rate | level | USA | neutral | monthly (~1mo lag) | CPI, year over year | \<external\> |
| inflation_rate | level | Japan | neutral | monthly (~1mo lag) | BoJ CPI | \<external\> |
| inflation_rate | level | Spain/Eurozone | neutral | monthly (~1mo lag) | ECB HICP | \<external\> |
| inflation_rate | level | Global aggregate | neutral | monthly (~1mo lag) | weighted blend of the above | \<derived\> (currently USA-only until Japan/Spain sources exist) |
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

The `<derived>` market-cycle rows are computed in `doc/calculations.md` §18:

- `inflation_rate_trend` and `real_interest_rate_trend`: trend direction, §18.1.
- `real_interest_rate`: nominal policy rate minus inflation, §18.2.

`policy_rate` and `policy_rate_trend` are the nominal policy rate and the
nominal rate trend required by the Investment Market Cycle (HLD §10).

## 3. Data Availability & Limitations

- M2 (all markets) and all Japan/Spain macro readings are `<external>` today;
  committed to building a separate source for all of them rather than dropping
  any.
- `inflation_rate` is `<external>` for every market. The inflation levels feed
  the state engine; a source (FRED, BoJ, ECB) is not built yet.
- The Global aggregate macro rows are `<derived>`, but until Japan/Spain
  sources exist that "aggregate" is effectively USA-only.
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
