# Plan — Tax Page

**Status**: implemented (Phase 3)
**Depends on**: Fiscal-Rules P&L Engine, Phases 1–2 of `doc/plans/fiscal_rules_pnl_engine.md`.

## Purpose

Review taxable P&L per fiscal year, reusing the fiscal-rule P&L engine. The ruleset now extends beyond sell conversion: it also defines a **fiscal-year start** and covers **dividends** as a taxable item type.

## Design

### Ruleset extension (§17.1)

The ruleset key (`spain`, `japan`, `default`, `latest`, `none`) now bundles:

- **Realized-gains conversion** (existing §16.2).
- **Fiscal-year start** `(month, day)`. v1 uses the natural year `(1, 1)` for all rulesets (Spain and Japan both tax individuals on the natural year); the field is configurable so a ruleset like Japan can use an April-to-March year per topic later.
- **Dividend treatment**: dividends are taxable income, not sells — they convert at their `payment_date` (fallback `timestamp`) rate, independent of the sell-conversion rules.

### Taxable P&L (§17.2–§17.4)

`GET /analytics/taxable-pnl?display_currency=&locale=&ruleset=` groups **realized gains + dividends** into fiscal years of the report ruleset (default = locale-derived):

- **Realized gains**: each sell's taxable amount = `convert_sale` under its frozen `fiscal_rule` (locale fallback), then exemption applied; losses pass through.
- **Dividends**: gross `total_value` converted at the payment date, then exemption applied.
- **Exemption** (`transactions.fiscal_exemption_id`): for a positive amount `g` with exemption `e`:
  - `rate_exempt = g × e.exemption_rate/100` (capped by `e.exemption_rate_limit` when set);
  - `fixed = e.exemption_amount` converted from the transaction currency at the tx date;
  - `taxable = g − min(g, rate_exempt + fixed)`. Losses are never reduced.

### Response

`TaxablePnlSummary { ruleset, display_currency, fiscal_years[], total_taxable, rate_fallbacks }`; each year has `fiscal_year`, `start_date`, `end_date`, `realized_gains_taxable`, `dividends_taxable`, `total_taxable`, `num_sells`, `num_dividends`. Rate fallbacks (`realized_pl | invested_historic | dividends`) surface the closest-in-time warnings.

## Out of scope

- Fiscal-year / country tax-form mapping beyond the fiscal-year start.
- Tax rates or loss carry-forward.
- CSV/PDF export.
