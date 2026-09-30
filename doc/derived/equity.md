# Derived Equity KPIs

> Equity KPIs computed from fetchers' fields or from other KPIs. The fetched
> equity KPIs they build on live in `doc/kpis/world.md`. Macro derived KPIs live
> in `doc/derived/macro.md`.

`kpi_name, kind, section, favorable_direction, source`

| kpi_name | kind | section | favorable_direction | source |
|---|---|---|---|---|
| revenue_growth_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| gross_margin_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| operating_margin_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| roe_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| roic | level | fundamentals | higher_better | \<derived\> |
| roic_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| net_debt_to_equity | level | fundamentals | lower_better | \<derived\> |
| net_debt_to_equity_trend_5y | trend | fundamentals | lower_better | \<derived\> |
| interest_coverage_ebit | level | fundamentals | higher_better | \<derived\> |
| interest_coverage_ebit_trend_5y | trend | fundamentals | higher_better | \<derived\> |
| fcf_conversion | level | fundamentals | higher_better | \<derived\> |
| fcf_conversion_trend_5y | trend | fundamentals | higher_better | \<derived\> |
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
  `doc/derived/macro.md`.
