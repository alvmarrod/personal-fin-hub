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
- Validation happens before import: FK checks, snapshot constraints, data format
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

- Must respect snapshot constraints: imported transactions cannot precede existing snapshots for the same `(entity, currency)` pair
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

**Trigger**: User reviews taxable profit/loss per fiscal period (future page)

**Modeling decision**:

- Reuses the fiscal-rule P&L engine: each sell is converted per the rule active at its date.
- Fiscal-year / country tax-form mapping and `fiscal_exemptions` integration are future scope.

**Entities affected**: `fiscal_periods` (read), `transactions` (read), `fiscal_exemptions` (read)

**UI pages**: TBD (future Tax page)

**See**: `doc/plans/tax_page.md`

**Status**: 📋 Planned
