# Tier 9 — Planned

Operations that are designed but not yet implemented. These use cases define the intended modeling for future development.

---

## UC-41: Portfolio Rebalancing

**Trigger**: User wants to rebalance their portfolio to match target allocations (desired_weight on portfolio_assets)

**Modeling decision**:

- Rebalancing is a compound operation: sell overweights + buy underweights
- Each leg is an individual transaction (INVESTMENT_SELL or INVESTMENT_BUY)
- The batch is NOT atomic — some legs may succeed while others fail (partial rebalance is acceptable)
- `investment_transaction_category = 'REBALANCE'` marks these transactions for filtering
- Rebalance is a manual operation only — never scheduled. Scheduled investment purchases are always stamped `DCA`.

**Modeling alternatives under consideration**:

- **Option A**: Individual transactions per leg (like batch import). Simple, works with existing analytics. User executes each leg separately.
- **Option B**: Single `POST /transactions/batch` with all legs. Atomic. User sees the full rebalance as one operation.
- **Option C**: Dedicated rebalance endpoint that computes the required trades and executes them. Most automated but most complex.

**Decision pending**: Which option best balances simplicity with user control.

**Currency model**:

- Each leg follows the same currency rules as UC-08/UC-09
- Cross-currency rebalancing (selling USD ETF, buying EUR ETF) involves multiple currencies
- FX rates are per-leg, not shared across the rebalance

**Entities affected**: `transactions` (write × N), `portfolio_assets` (read for desired_weight)

**UI pages**: TBD (likely Portfolio Assets page or dedicated Rebalance page)

**Status**: 📋 Planned

---

## UC-42: CSV Import

**Trigger**: User bulk-loads historical transactions from a CSV/Excel file

**Modeling decision**:

- CSV is parsed client-side into a list of transaction objects
- Each row maps to a transaction following the same rules as UC-06 through UC-10
- Validation happens before import: FK checks, balance reconciliation, data format
- Import uses `POST /transactions/batch` (UC-13) for atomic execution

**Modeling alternatives under consideration**:

- **Option A**: Client-side CSV parsing → validation → batch API. Simple, no backend changes needed for parsing.
- **Option B**: Server-side CSV parsing endpoint. More robust validation but adds backend complexity.
- **Option C**: Two-phase import: upload CSV → preview/validate → confirm import. Most user-friendly but most complex.

**Decision pending**: Which option provides the best UX for historical data import.

**Currency model**:

- CSV columns must include: timestamp, type, entity (name or ID), currency, amount
- Optional columns: portfolio_asset (market_code), quantity, unit_price, payment_currency, fx_rate
- Cross-currency transactions in CSV follow the same rules as UC-06-10
- Missing FX rates are auto-resolved from the `currencies` table (if available for that date)

**Constraints**:

- Follows the Tier 5 Reconciliation Model: imported transactions may precede existing snapshots for the same `(entity, cash_pocket)` pair (cash_pocket = `COALESCE(payment_currency, currency)`); cash-impacting rows reconcile via the next snapshot's adjustment (and spends may inject inferred cash)
- Must validate all FK references before import
- Must handle duplicate detection (avoid importing the same transaction twice)

**Entities affected**: `transactions` (write × N)

**UI pages**: TBD (likely Transactions page with import button)

**Status**: 📋 Planned

---

## UC-47: Manage Fiscal Rules & Periods

**Trigger**: User selects which fiscal rule governs P&L display conversion over time (e.g., moving from one tax regime to another)

**Modeling decision**:

- Rules are a fixed, code-defined registry (`PnlRule`): `spain`, `japan`, `default` (copy of `spain`), `latest` (legacy), `none` (no rule → converts as `default`). The user never defines formulas — only *assigns* existing rules to time periods.
- A `fiscal_periods` row assigns a `rule_key` to a date range, scoped to a profile. Overlapping periods within a profile are rejected; `end_date` NULL = open-ended.
- The rule applied to an operation is resolved by its **sell date** (the period containing it) and **frozen at transaction creation** (`transactions.fiscal_rule` snapshot). Editing periods later never recomputes past operations; editing a sell's own timestamp re-resolves its snapshot.
- No period matches → `fiscal_rule` stays NULL and the read path falls back to the rule inferred from the user's locale (fallback `default`).

**Entities affected**: `fiscal_periods` (write), `transactions` (write, `fiscal_rule` snapshot)

**API**: `GET/POST/PUT/DELETE /fiscal-periods`

**UI pages**: Settings (`/settings`) — "Fiscal Rules" section

**See**: `doc/plans/fiscal_rules_pnl_engine.md` (Phase 2)

**Status**: ✅ Implemented

---

## UC-48: View Taxable P&L (Tax Page)

**Trigger**: User reviews taxable profit/loss per fiscal year

**Modeling decision**:

- Reuses the fiscal-rule P&L engine: each sell is converted per the rule active at its date (frozen snapshot), and dividends are added as taxable income converted at their payment date.
- The ruleset also defines the **fiscal-year start** used to group items (`spain`/`japan` = natural year in v1).
- `fiscal_exemptions` reduce the taxable amount of linked transactions (rate % exempt, optional fixed allowance, optional cap).

**Entities affected**: `fiscal_periods` (read), `transactions` (read), `fiscal_exemptions` (read)

**API**: `GET /analytics/taxable-pnl?display_currency=&locale=&ruleset=`

**UI pages**: Tax page (`/tax`)

**See**: `doc/plans/tax_page.md`, `calculations.md` §17

**Status**: ✅ Implemented

---

## UC-49: Manage Tax Rates

**Trigger**: User configures tax brackets/rates per ruleset, category, and year (e.g., updating Spain's progressive savings-income bands for a new tax year)

**Modeling decision**:

- Tax rates are **data** (not code), stored in the `tax_rates` table. The `TaxModel` (code) defines *how* to compute; `tax_rates` defines *what rates* to use.
- Each row is a bracket: `ruleset_key`, `category` (`capital_gains` / `dividends`), `from_amount`, `to_amount` (NULL = unbounded), `rate` (fraction), `year_start` (NULL = default for all years).
- Flat rate = one row per category (`from_amount=0`, `to_amount=NULL`). Progressive = multiple rows with ascending bands.
- Profile-scoped via `profile_id` for per-profile overrides.
- Initial rates seeded per ruleset in migration 013 (Spain progressive 19/21/23%, Japan flat 20.315%, default = copy of Spain).

**Entities affected**: `tax_rates` (write)

**API**: `GET/POST/PUT/DELETE /tax-rates`

**UI pages**: Settings (`/settings`) — "Tax Rates" section

**See**: `doc/plans/tax_page.md`, `calculations.md` §17.8

**Status**: 📋 Planned

---

## UC-50: View Tax Owed (per fiscal year)

**Trigger**: User reviews tax owed per fiscal year, including per-item detail and confirmed-vs-computed resolution

**Modeling decision**:

- Extends UC-48 (Taxable P&L): each fiscal year now includes `tax_owed` (computed from ruleset brackets, §17.9), `confirmed_tax` (from `transaction_taxes`, §17.10), and `items[]` (per-item detail).
- Tax resolution: `tax = confirmed if present else computed`, with source flag (`confirmed` / `computed`).
- `SavingsCombined` model: gains + dividends share progressive brackets; combined base split proportionally back.
- `FlatPerCategory` model: flat rate per category, no combining.
- Items show: kind, instrument, date, taxable_amount, rule, tax_owed, confirmed_tax, source.
- Year rows are expandable (inline drill-down) to show itemized transactions.

**Entities affected**: `tax_rates` (read), `transaction_taxes` (read), `transactions` (read), `fiscal_exemptions` (read)

**API**: `GET /analytics/taxable-pnl` (extended response with `tax_owed`, `confirmed_tax`, `items[]`, `combined_base`, `default_ruleset`)

**UI pages**: Tax page (`/tax`) — expandable year rows, tax column with source badges

**See**: `doc/plans/tax_page.md`, `calculations.md` §17.9–§17.12

**Status**: 📋 Planned

---

## UC-51: Set Profile Default Ruleset

**Trigger**: User overrides the locale-inferred default ruleset for their profile

**Modeling decision**:

- `profiles.default_fiscal_rule TEXT` (nullable): user-override for the default ruleset.
- Null = locale-inferred (existing behavior: `es` → `spain`, `ja` → `japan`, else `default`).
- Non-null = user's explicit choice (e.g., `japan` for a Japanese user living in Spain).
- **Write-time snapshot**: `fiscal_periods` (by date) → `profiles.default_fiscal_rule` → NULL.
- **Read-time effective**: `rule_for_locale` (locale inference). Per-item `fiscal_rule = snapshot or resolved_ruleset`.
- Surfaced in Settings (read + edit) and on the Tax page header.

**Entities affected**: `profiles` (write)

**API**: `GET/PATCH /profiles/{id}` (exposes `default_fiscal_rule`)

**UI pages**: Settings (`/settings`) — default ruleset display/edit; Tax page (`/tax`) — header shows resolved default

**See**: `doc/plans/tax_page.md`, `calculations.md` §17.13

**Status**: 📋 Planned
