# Tier 9 — Planned

Operations that are designed but not yet implemented. These use cases define the intended modeling for future development.

> **Timezone note**: UC-42 (CSV Import) timestamps must be interpreted in the profile timezone. UC-47 (Fiscal Periods) `start_date`/`end_date` are profile-tz calendar dates. See `doc/timezone_model.md`.

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
- The rule applied to an operation is resolved by its **operation date** — the sell date, or the `payment_date` (fallback `timestamp`) for a dividend — (the period containing it) and **frozen at transaction creation** (`transactions.fiscal_rule` snapshot). Editing periods later never recomputes past operations; editing a transaction's own date re-resolves its snapshot.
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

## UC-49: Manage Tax Bases & Definitions

**Trigger**: User configures a ruleset's annual tax computation (brackets or flat rate) and its per-operation tax/levy definitions (e.g., updating Spain's progressive savings-income bands for a new tax year, or adding Spain's Tasa Tobin)

**Modeling decision**:

- Annual tax computation and per-operation levies are both **data** (not code), replacing the `TaxModel` classes and the `tax_rates` table. See `doc/plans/tax_definitions_engine.md`.
- `tax_bases`: one row per ruleset (+ optional `year_start`), declares `computation` (`progressive` or `flat`) and, for flat, the rate directly. `tax_base_categories` declares which income categories (`capital_gains`/`dividends`/`interest`) feed it — fixed per ruleset, not year-versioned. `tax_base_rates` holds bracket rows, only when `computation = 'progressive'`.
- `tax_definitions`: per-operation taxes/levies (Tasa Tobin, foreign withholding), each with a stable `slug`, an optional `ruleset_key` (NULL = generic, e.g. foreign withholding), and a `rate` (NULL/0 = never auto-applies — always user-entered).
- `broker_fee_definitions`: a parallel, ruleset-independent catalog (name only) for naming broker commissions — same CRUD pattern, no formula.
- No profile-level overrides on any of these tables (unlike the old `tax_rates.profile_id`) — a user corrects a specific operation's amount via a confirmed `transaction_taxes` row (UC-50) instead, never the definition's own rate.
- Initial rows seeded per ruleset (Spain `progressive` with its own bracket set, Japan `flat` with its own rate, `default` = copy of Spain) — exact rates/brackets TBD at seeding time, not specified in this document; migration TBD, not yet applied (Phase 1: docs only).

**Entities affected**: `tax_bases`, `tax_base_categories`, `tax_base_rates`, `tax_definitions`, `broker_fee_definitions` (write)

**API**: `GET/POST/PUT/DELETE /tax-bases`, `/tax-definitions`, `/broker-fee-definitions`

**UI pages**: Settings (`/settings`) — replaces the "Tax Rates" section

**See**: `doc/plans/tax_definitions_engine.md`

**Status**: 📋 Planned

---

## UC-50: View Tax Owed (per fiscal year)

**Trigger**: User reviews tax owed per fiscal year, including per-item detail and confirmed-vs-computed resolution

**Modeling decision**:

- Extends UC-48 (Taxable P&L): each fiscal year now includes `tax_owed` (computed from the ruleset's `tax_bases`, §17.9), and `items[]` (per-item detail).
- Tax resolution is now per `tax_definitions`-linked row, not per category: a confirmed `transaction_taxes` row overrides only its own definition's amount (§17.11) — `withholding`/Tasa-Tobin-style rows resolve independently of the item's core computed tax.
- `computation = 'progressive'` rulesets (Spain): gains + dividends + interest share one bracket table (`tax_base_categories`); combined base, taxed per item in chronological bracket order (decision 10).
- `computation = 'flat'` rulesets (Japan): flat rate per category, no combining.
- Items show: kind, instrument, date, taxable_amount, rule, tax_owed, and each linked `tax_definitions` row's own confirmed/computed resolution.
- Year rows are expandable (inline drill-down) to show itemized transactions.

Each item's own `tax_owed` is computed by where it falls chronologically as the year's brackets fill up (decision 10 in `doc/plans/tax_definitions_engine.md`), not by a proportional split. Foreign withholding is deducted from the year's `total_tax` only — pooled at the whole `tax_bases` row, never attributed back to individual items (decision 8). Manually overriding the final combined `tax_owed` does not apply (decision 9); the user can still correct any individual `transaction_taxes` row, never the combined total directly.

**Entities affected**: `tax_bases` (read), `tax_definitions` (read), `transaction_taxes` (read), `transactions` (read), `fiscal_exemptions` (read)

**API**: `GET /analytics/taxable-pnl` (extended response with `tax_owed`, `items[]`, `combined_base`, `default_ruleset`)

**UI pages**: Tax page (`/tax`) — expandable year rows, tax column with source badges

**See**: `doc/plans/tax_page.md`, `doc/plans/tax_definitions_engine.md`, `calculations.md` §17.9–§17.12

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
