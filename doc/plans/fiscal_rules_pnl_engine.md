# Plan — Fiscal-Rules P&L Engine

**Status**: active
**Depends on**: Performance page improvements (currency selector + delta styling, PR #36). No dependency on the Market API outage plan.
**Scope**: correctness of realized-P&L display-currency conversion, plus a rule-based engine that lets the user's fiscal regime (which may change over time) drive how each operation is converted to the display currency. Foundational work for a future Tax page.

## Problem

The performance summary (`get_performance_summary`) converts realized P&L and invested historic to the display currency using today's (latest) rate. Fiscal regimes compute taxable gain differently (e.g., Spain converts the native P&L at the sale-day rate; Japan converts sale and purchase legs each at their own day's rate), and a user's regime can change over time (move to another country, law change). Each past operation was performed under the regime in force at that time and must not be recomputed when the user later changes their regime.

This plan defines an engine where:

- the **native** realized P&L per sell is computed once, rule-independent, via true FIFO lots;
- each rule only defines **how the display currency conversion** is applied to the sale and its consumed lots;
- the rule applied to an operation is resolved by its **sell date** and **frozen at transaction creation**.

## Design decisions (confirmed)

1. **Native P&L is rule-independent.** All rules share the same native gain `sell_total − cost_basis` (asset currency) computed from a FIFO lot queue. Rules differ only in display-currency conversion. The realized-gains table therefore stays rule-independent; only the summary cards are rule-dependent.
2. **Rules are code; assignments are data.** The set of formulas is finite and versioned → a code registry (`PnlRule` abstraction). Only the user's choice over time is stored in the DB (`fiscal_periods`).
3. **Rule resolution is per operation by sell date, frozen at creation.** The rule active on the sell date is snapshotted onto the transaction when it is created. Later edits to fiscal periods never retroactively change past operations.
4. **Invested historic is buy-side only.** It is always converted per `INVESTMENT_BUY` at the buy-date rate, independent of any fiscal rule (it is about invested cash, not performance). Tooltip must say so.
5. **Missing historical rate → closest available in time + flag + warn.** The calculation uses the closest stored rate in time; the response flags the fallback and the UI warns the user to provide the manual rate for accuracy.
6. **Default rule from locale.** The default rule is inferred from the user's locale; a generic `default` rule (a copy of the Spain rule) is used for locales without a country rule in the ruleset. "No rule" is supported explicitly.
7. **Proceeds currency is captured by `payment_currency`/`fx_rate` on the sell.** Empty `payment_currency` = proceeds stay in the asset currency; set = proceeds are received/converted to that currency at sell time. UI labeling clarified to "proceeds received in".

## Ruleset v1

| key | Name | Display conversion of a sell at date `T` |
|-----|------|------------------------------------------|
| `spain` | Spain (constant sale-day rate) | `(sell_total − cost_basis) × rate(asset→display, T)` |
| `japan` | Japan (FX-aware) | `sell_total × rate(asset→display, T) − Σ lot_cost × rate(asset→display, lot.buy_date)` over consumed lots |
| `default` | Default (copy of `spain`) | same as `spain` |
| `latest` | Legacy / current behavior | native P&L × latest available rate (kept for migration parity) |

When the sell records `payment_currency` + `fx_rate`, proceeds are realized in `payment_currency` and converted from `payment_currency → display` (see Phase 1).

## Phases

### Phase 0 — Documentation alignment (this task)

Update the docs to describe the target design before implementation.

- [x] Roadmap docs (this file + `doc/plans/tax_page.md`)
- [x] `doc/use_cases.md` — UC-47, UC-48 planned entries
- [x] `doc/uc_9_planned.md` — UC-47 / UC-48 bodies
- [x] `doc/subsystems/database.md` — `fiscal_periods` table + `fiscal_rule` snapshot column (planned)
- [x] `doc/calculations.md` — §10.1 lots carry `buy_date`; new §16 fiscal-rule conversion; invested-historic rule
- [x] `doc/calculations_inventory.md` — Performance page rows
- [x] `doc/uc_7_analytics_reads.md` — UC-32 / UC-34 planned-evolution notes
- [x] `doc/uc_2_core_transactions.md` — UC-09 proceeds-currency note
- [x] `doc/uc_4_schedules.md` — DCA stamping note (from the transaction-category task)

### Phase 1 — P&L engine foundation

- [x] Convert `get_realized_gains` to **true FIFO lots carrying `buy_date`** (`{quantity, unit_cost, buy_date}`). This aligns the code with `calculations.md` §10/§11, which already specify FIFO (the current implementation is a moving average).
- [x] Add the `PnlRule` abstraction + registry: `spain`, `japan`, `default` (copy of `spain`), `latest` (legacy).
- [x] Proceeds currency: honor `payment_currency`/`fx_rate` on the sell (proceeds realized in `payment_currency`, converted at sell date; otherwise proceeds in asset currency, converted at sell date).
- [x] Route `get_performance_summary` realized + invested-historic through the engine; invested historic converted per-buy at buy-date rates (rule-independent).
- [x] Update tooltips (EN + ES): `performance.hintRealizedPL`, `performance.hintTotalInvestedHistoric` explain same-currency vs cross-currency and the two rates used.
- [x] Rate fallback: closest-in-time rate + flag in the API response + warning on the Performance page.
- [x] Default rule from user locale (`locale → country → rule`, fallback `default`).
- [x] Tests (FIFO lots, both rules, proceeds currency, invested historic, fallback flag), changelog, version bump, doc sync.

### Phase 2 — Fiscal periods

- [x] `fiscal_periods` table (profile-scoped: `profile_id`, `rule_key`, `start_date`, `end_date`) + migration.
- [x] Rule snapshot at transaction creation (`transactions.fiscal_rule`) — guarantees past operations never change when periods are edited.
- [x] CRUD API + routes + tests.
- [x] Settings page (`/settings`) section to manage periods (add/edit/remove rule + date range).
- [x] Resolution: sell date → containing period → rule; no period → profile `default_fiscal_rule` backfill; no period + no profile default → NULL snapshot; explicit "no rule" (`none`) honored.

> **Designed-vs-implemented note**: The original proposal read the profile default at
> read time to override the locale-inferred ruleset. The merged implementation
> backfills the profile default at write time only; the read-time effective ruleset
> is still `rule_for_locale` (locale inference). Both are non-breaking; no runtime
> behavior was reverted.

### Phase 3 — Tax reporting

- [x] Tax page (`/tax`) — taxable P&L per fiscal year (see `doc/plans/tax_page.md`).

### Phase 4 — Tax System Expansion

- [x] `tax_rates` table + migration (ruleset_key, category, from_amount, to_amount, rate, year_start, profile_id) + seeded rates for spain/japan/default.
- [x] `profiles.default_fiscal_rule` column + migration (nullable; overrides locale-inferred default).
- [x] TaxModel engine: `TaxModel` protocol + `SavingsCombinedTaxModel` (Spain: combined progressive brackets) + `FlatPerCategoryTaxModel` (Japan: flat per category). `TAX_CATEGORIES` dict, `TAX_MODELS` registry, `_apply_progressive` helper.
- [x] Tax rates CRUD: `services/tax_rate_svc.py`, `routes/tax_rates.py`, `db/queries.py` extensions.
- [x] Analytics extension: `get_taxable_pnl` returns `tax_owed`, `confirmed_tax`, `items[]`, `combined_base`, `default_ruleset` per fiscal year.
- [x] Confirmed tax aggregation from `transaction_taxes` (formalized `tax_type` vocabulary).
- [x] Tax resolution: `confirmed if present else computed`, source flag per item.
- [x] Profile default ruleset: get/set on profiles, surfaced in Settings + Tax page header.
- [x] Frontend: expandable year rows with item detail (rule, tax, source badge).
- [x] Frontend: Tax Rates Settings section + `TaxRateModal` CRUD.
- [x] Frontend: default ruleset display/edit in Settings.
- [x] i18n keys (EN + ES): `taxRates.*`, `tax.items.*`, `tax.source.*`, `fiscalRules.default`.
- [x] Tests: model computation (~30), CRUD + seeding (~15), analytics extension (~10), profile default (~3).
- [x] Docs: `tax_page.md`, `calculations.md` §17, `calculations_inventory.md`, `database.md`, `api_endpoints.md`, `use_cases.md`, `uc_9_planned.md`, `workflow.md`, `uc_7_analytics_reads.md`.
- [x] Gates: ruff, mypy, svelte-check, build, validate-i18n, changelog-check, version bumps.

See `doc/plans/tax_page.md` for the full design.

## Gates

- Backend: `pytest` (full suite), `ruff`, `mypy`.
- Frontend: `bun run test`, `bun run build`, `bun run validate-i18n`.
- `python3 scripts/changelog-check.py`; version bumps per release when folded in.
- `doc/calculations_inventory.md` kept green (statuses updated with each phase).

## Out of scope

- Cash-position tracking of proceeds after conversion (what the user does with the money later).
- Per-asset rule overrides — periods only.
- Fiscal-year tax forms, tax-lot export, CSV export.
- Changes to unrealized P&L conversion (stays at latest market rates — it is current-state, not rule-driven).
