# Macro Pairings & Aggregation

Configuration for how equity KPIs pair with macro KPIs and how alignment
scores aggregate. KPI definitions live in `doc/kpis/world.md`;
every `kpi_name` below is a foreign key into that registry. Scoring method
and banding live in `doc/systems/asset_evaluation/methodology.md`. No
implementation code.

## 1. Macro-Pairing Reference

Market-agnostic — `macro_kpi_name` below refers to the *concept*
(`policy_rate`, `m2_growth`, `yield_curve_slope`); it resolves to the
specific stock's primary listing market (or global aggregate fallback) at
evaluation time, per the parent HLD (Section 7 of `asset_evaluation_methodology.md`).

| Equity KPI category | Paired macro KPI | Rationale |
|---|---|---|
| net_debt_to_equity, interest_coverage_ebit | policy_rate | Debt is more expensive/risky as rates rise |
| gross_margin, operating_margin, roe, roic | m2_growth | Loose money conditions typically support pricing power and demand |
| pe_ratio, ev_ebit, p_fcf | yield_curve_slope | Multiple compression is more expected in a flattening/inverting curve |
| shareholder_yield | policy_rate | Yield attractiveness is judged relative to the risk-free rate, not the curve shape |
| revenue_growth, fcf_conversion | none | No clear single macro counterpart — 2-input alignment (level + trend only) |

## 2. Aggregation Table

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
