# KPI Catalog & Macro Pairings

Companion to the Asset Evaluation Methodology HLD. Catalogs every equity KPI,
every macro KPI, and their pairing/aggregation configuration — ready for a
`yfinance`-based implementation. No implementation code.

**Sourcing convention** used in every `yfinance_name` column:

- literal value → actual `yfinance` field or ticker
- `<calculated>` → not a single field, but derivable from `yfinance`-exposed
  data
- `<not in yfinance>` → not available from `yfinance` at all; requires a
  different source (still fully specified here, for later implementation)

## 1. Peer Universe

The sector-quartile bands (Section 3) require a peer group per GICS sector.
Peer universe, per market:

| Market | Universe | Approx. size |
|---|---|---|
| USA | S&P 500 constituents | ~500 |
| Japan | TOPIX constituents | ~2,000 |
| Spain | IBEX 35 constituents | 35 |

- **Universe membership itself is `<not in yfinance>`** — yfinance has no
  index-constituents endpoint; it only serves per-ticker data. Membership
  lists need a separate, periodically-refreshed source (e.g. a maintained
  public reference list), fetched independently of the per-KPI pulls in
  this document.
- **IBEX 35 caveat**: 35 names is thin for computing per-GICS-sector
  quartiles — several sectors will have very few (or zero) Spanish
  constituents, making those bands low-confidence until the universe is
  broadened (e.g. to a wider Spanish/Eurozone index) in a later phase.

## 2. Sector Classification Reference

All equity KPI bands are computed relative to **GICS sector** (per the
parent HLD). Sourced from `yfinance`'s `info['sector']` field
(`info['industry']` available if finer granularity is ever needed).

## 3. Banding Convention (equity KPIs)

Default rule, applied to every equity KPI unless noted otherwise:

- **Sector quartile split**: bottom 25% = red, middle 50% = yellow, top
  25% = green — direction-adjusted per KPI's `favorable_direction`.
- **Trend rows** use the same quartile convention, applied to the
  distribution of trailing slopes within the sector rather than levels.

## 4. Equity KPI Table

`kpi_name, kind, section, favorable_direction, yfinance_name`

| kpi_name | kind | section | favorable_direction | yfinance_name |
|---|---|---|---|---|
| revenue_growth | level | fundamentals | higher_better | revenueGrowth |
| revenue_growth_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| gross_margin | level | fundamentals | higher_better | grossMargins |
| gross_margin_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| operating_margin | level | fundamentals | higher_better | operatingMargins |
| operating_margin_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| roe | level | fundamentals | higher_better | returnOnEquity |
| roe_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| roic | level | fundamentals | higher_better | \<calculated\> |
| roic_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| net_debt_to_equity | level | fundamentals | lower_better | \<calculated\> |
| net_debt_to_equity_trend_5y | trend | fundamentals | lower_better | \<calculated\> |
| interest_coverage_ebit | level | fundamentals | higher_better | \<calculated\> |
| interest_coverage_ebit_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| fcf_conversion | level | fundamentals | higher_better | \<calculated\> |
| fcf_conversion_trend_5y | trend | fundamentals | higher_better | \<calculated\> |
| pe_ratio | level | valuation | lower_better | trailingPE |
| pe_ratio_trend_5y | trend | valuation | lower_better | \<calculated\> |
| ev_ebit | level | valuation | lower_better | \<calculated\> |
| ev_ebit_trend_5y | trend | valuation | lower_better | \<calculated\> |
| p_fcf | level | valuation | lower_better | \<calculated\> |
| p_fcf_trend_5y | trend | valuation | lower_better | \<calculated\> |
| shareholder_yield | level | valuation | higher_better | \<calculated\> |
| shareholder_yield_trend_5y | trend | valuation | higher_better | \<calculated\> |

Notes on `<calculated>` fields:

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
  `.balance_sheet` / `.cashflow` — see Section 6.

## 5. Macro KPI Table

`kpi_name, kind, market, favorable_direction, update_frequency, source_note, yfinance_name`

| kpi_name | kind | market | favorable_direction | update_frequency | source_note | yfinance_name |
|---|---|---|---|---|---|---|
| policy_rate | level | USA | lower_better | event-driven (~8x/yr) | 13-week T-bill yield as proxy | \<calculated\> |
| policy_rate_trend | trend | USA | lower_better | event-driven | slope of the above | \<calculated\> |
| policy_rate | level | Japan | lower_better | event-driven | BOJ policy rate | \<not in yfinance\> |
| policy_rate_trend | trend | Japan | lower_better | event-driven | slope of BOJ policy rate | \<not in yfinance\> |
| policy_rate | level | Spain/Eurozone | lower_better | event-driven | ECB deposit rate | \<not in yfinance\> |
| policy_rate_trend | trend | Spain/Eurozone | lower_better | event-driven | slope of ECB deposit rate | \<not in yfinance\> |
| yield_curve_slope | level | USA | higher_better | daily | 10Y (^TNX) minus 3M (^IRX) | \<calculated\> |
| yield_curve_slope_trend | trend | USA | higher_better | daily | slope of the above | \<calculated\> |
| yield_curve_slope | level | Japan | higher_better | daily | JGB 10Y minus short-end | \<not in yfinance\> |
| yield_curve_slope_trend | trend | Japan | higher_better | daily | slope of the above | \<not in yfinance\> |
| yield_curve_slope | level | Spain/Eurozone | higher_better | daily | Bund/Bono 10Y minus short-end | \<not in yfinance\> |
| yield_curve_slope_trend | trend | Spain/Eurozone | higher_better | daily | slope of the above | \<not in yfinance\> |
| m2_growth | level | USA | higher_better | monthly (~1mo lag) | FRED M2SL, YoY % | \<not in yfinance\> |
| m2_growth_trend | trend | USA | higher_better | monthly | slope of the above | \<not in yfinance\> |
| m2_growth | level | Japan | higher_better | monthly | BOJ money stock stats | \<not in yfinance\> |
| m2_growth_trend | trend | Japan | higher_better | monthly | slope of the above | \<not in yfinance\> |
| m2_growth | level | Spain/Eurozone | higher_better | monthly | ECB money supply stats | \<not in yfinance\> |
| m2_growth_trend | trend | Spain/Eurozone | higher_better | monthly | slope of the above | \<not in yfinance\> |
| policy_rate / yield_curve_slope / m2_growth (+ trends) | level & trend | Global aggregate | (same as above) | (same as above) | weighted blend of USA/Japan/Spain readings | \<calculated\> (currently USA-only until Japan/Spain sources exist) |

## 6. Macro-Pairing Reference

Market-agnostic — `macro_kpi_name` below refers to the *concept*
(`policy_rate`, `m2_growth`, `yield_curve_slope`); it resolves to the
specific stock's primary listing market (or global aggregate fallback) at
evaluation time, per the parent HLD (Section 7).

| Equity KPI category | Paired macro KPI | Rationale |
|---|---|---|
| net_debt_to_equity, interest_coverage_ebit | policy_rate | Debt is more expensive/risky as rates rise |
| gross_margin, operating_margin, roe, roic | m2_growth | Loose money conditions typically support pricing power and demand |
| pe_ratio, ev_ebit, p_fcf | yield_curve_slope | Multiple compression is more expected in a flattening/inverting curve |
| shareholder_yield | policy_rate | Yield attractiveness is judged relative to the risk-free rate, not the curve shape |
| revenue_growth, fcf_conversion | none | No clear single macro counterpart — 2-input alignment (level + trend only) |

## 7. Aggregation Table

`equity_kpi_name, w1, equity_trend_kpi_name, w2, macro_kpi_name, w3, macro_trend_kpi_name, w4, b1_limit, b2_limit, b3_limit, b4_limit, b5_limit`

Default bucket limits (same for every row, tunable later):
`b1=-0.67, b2=-0.33, b3=0.00, b4=0.33, b5=0.67` — mapping `alignment_raw`
in `[-1,1]` to a 0–5 score.

| equity_kpi_name | w1 | equity_trend_kpi_name | w2 | macro_kpi_name | w3 | macro_trend_kpi_name | w4 | b1 | b2 | b3 | b4 | b5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| revenue_growth | 0.5 | revenue_growth_trend_5y | 0.5 | n/a | 0 | n/a | 0 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| gross_margin | 0.25 | gross_margin_trend_5y | 0.25 | m2_growth | 0.25 | m2_growth_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| operating_margin | 0.25 | operating_margin_trend_5y | 0.25 | m2_growth | 0.25 | m2_growth_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| roe | 0.25 | roe_trend_5y | 0.25 | m2_growth | 0.25 | m2_growth_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| roic | 0.25 | roic_trend_5y | 0.25 | m2_growth | 0.25 | m2_growth_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| net_debt_to_equity | 0.25 | net_debt_to_equity_trend_5y | 0.25 | policy_rate | 0.25 | policy_rate_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| interest_coverage_ebit | 0.25 | interest_coverage_ebit_trend_5y | 0.25 | policy_rate | 0.25 | policy_rate_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| fcf_conversion | 0.5 | fcf_conversion_trend_5y | 0.5 | n/a | 0 | n/a | 0 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| pe_ratio | 0.25 | pe_ratio_trend_5y | 0.25 | yield_curve_slope | 0.25 | yield_curve_slope_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| ev_ebit | 0.25 | ev_ebit_trend_5y | 0.25 | yield_curve_slope | 0.25 | yield_curve_slope_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| p_fcf | 0.25 | p_fcf_trend_5y | 0.25 | yield_curve_slope | 0.25 | yield_curve_slope_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |
| shareholder_yield | 0.25 | shareholder_yield_trend_5y | 0.25 | policy_rate | 0.25 | policy_rate_trend | 0.25 | -0.67 | -0.33 | 0 | 0.33 | 0.67 |

## 8. Data Availability & Limitations

- M2 (all markets) and all Japan/Spain macro readings are `<not in
  yfinance\>` today; committed to building a separate source for all of
  them rather than dropping any.
- The Global aggregate macro rows are `<calculated>`, but until Japan/Spain
  sources exist, that "aggregate" is effectively USA-only.
- yfinance typically exposes ~4 years of annual fundamentals — the 5y trend
  default from the parent HLD will run on a shorter available window until
  deeper history is sourced elsewhere.
- `info` dict fields (`trailingPE`, `returnOnEquity`, etc.) vary in
  reliability and coverage across tickers, and especially across non-US
  exchanges — an implementation-time risk this document doesn't resolve.
