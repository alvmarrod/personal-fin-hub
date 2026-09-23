# Plan — Tax Page & Tax System Expansion

**Status**: implemented
**Depends on**: Fiscal-Rules P&L Engine, Phases 1–3 of `doc/plans/fiscal_rules_pnl_engine.md`.

## Purpose

Provide a unified tax view per fiscal year that:

1. Shows **taxable P&L** (realized gains + dividends), reusing the fiscal-rule P&L engine.
2. Computes **tax owed** per year using an expansible tax-model abstraction (progressive brackets, combined or per-category, user-editable rates).
3. Surfaces **confirmed tax** (user-entered via `transaction_taxes`) alongside computed tax, resolving to one value per item.
4. Lets the user **manage tax rates** per ruleset/category/year in Settings.
5. Shows the **resolved default ruleset** (locale-inferred or per-profile override) and lets the user override it.
6. Provides **drill-down** on fiscal-year rows to see itemized transactions composing each year's tax.

## Implemented baseline (Phase 3)

Phase 3 delivered the foundational Tax page (`/tax`) with:

- Taxable P&L per fiscal year (realized gains + dividends, exemptions applied).
- Ruleset selector driving fiscal-year start and fallback rule.
- Display currency selector.
- Rate fallback warnings.

The design below extends this baseline with tax computation, confirmed-tax resolution, user-editable rates, and drill-down.

## Design

### Tax bases and definitions (§17.7–§17.8)

Annual/combined tax computation (Spain's progressive "base del ahorro", Japan's flat rate) and per-operation taxes (Tasa Tobin, foreign withholding) are both modeled as versioned data — `tax_bases`/`tax_base_categories`/`tax_base_rates` for the former, `tax_definitions` for the latter — replacing the hardcoded `TaxModel` classes (`SavingsCombinedTaxModel`/`FlatPerCategoryTaxModel`) and the `tax_rates` table. Broker fees are named via a parallel `broker_fee_definitions` catalog. Neither has per-profile overrides — a user corrects one operation's amount via a confirmed `transaction_taxes` row (§17.11), never the definition's own rate. See `doc/plans/tax_definitions_engine.md` for the full schema and design rationale.

#### v1 rulesets

| Ruleset | `tax_bases.computation` | Behavior |
|---|---|---|
| `spain`, `default` | `progressive` | Gains + dividends + interest share one progressive bracket table (Spain "savings income"). Combined base = sum of post-exemption category bases; tax computed on combined total; split proportionally back to categories. |
| `japan`, `latest`, `none` | `flat` | Flat rate per category, no combining. Each category taxed independently. |

Adding a new country = insert a `tax_bases` row (+ `tax_base_rates` if progressive) + any `tax_definitions` rows it needs.

### Tax categories (§17.6)

Extensible enum of taxable income types:

| Category | v1 status | Notes |
|---|---|---|
| `capital_gains` | Implemented | Realized gains from sells. |
| `dividends` | Implemented | Dividend income. |
| `salary` | Reserved | Future: work-income aggregation. |
| `interest` | Reserved | Future: interest income. |
| `other` | Reserved | Future: catch-all. |

### Computed tax (§17.9)

Per fiscal year, the engine:

1. Collects `bases[category]` = post-exemption taxable base (already computed by Phase 3).
2. Resolves the `tax_bases` row for the ruleset + year, and its `tax_base_categories` (which categories feed it) + `tax_base_rates` (if `computation = 'progressive'`).
3. Computes `tax_owed` per the base's own `computation` (below).

> **Pending (Decision 5, see `doc/plans/tax_definitions_engine.md`)**: how a per-item confirmed `tax_definitions` row (e.g. foreign withholding) credits against this computation is not yet defined — the formulas below are unchanged from today's behavior pending that decision.

#### `computation = 'progressive'` (Spain)

```text
combined_base = Σ bases[category]   # over each category in tax_base_categories
total_tax     = apply_progressive(combined_base, tax_base_rates)
tax_owed[category] = total_tax × (bases[category] / combined_base)   # proportional split
```

If `combined_base = 0`, all `tax_owed` are 0.

#### `computation = 'flat'` (Japan)

```text
tax_owed[category] = bases[category] × tax_bases.flat_rate
total_tax_owed = Σ tax_owed[category]
```

### Confirmed tax (§17.10)

Confirmed (actual) tax is stored per transaction in `transaction_taxes`, each row linked to a `tax_definitions` row via `tax_definition_id` (replaces the old `tax_type` free-text vocabulary):

- `tax_amount` = the user-entered amount, specific to that one `tax_definitions` row on that one transaction.
- Resolved per item, per definition — see §17.11. Not aggregated per category across the whole fiscal year the way the old `tax_type` vocabulary was.

> **Pending (Decision 5)**: how a user overrides their own annual combined `tax_owed` result (e.g. their actual final Spanish IRPF liability) — previously the `tax_type IN (capital_gains, dividends)` confirmed rows — has no defined home in this model yet. Only per-operation `tax_definitions` rows (Tasa Tobin, foreign withholding, and similar) resolve today, per §17.11. — see `doc/plans/tax_definitions_engine.md`.

### Tax resolution (§17.11)

Per `tax_definitions`-linked row on an item — not per item as a whole:

```text
tax    = confirmed_tax if a transaction_taxes row exists for this tax_definition_id
         else (rate × gross, if tax_definitions.rate is set, else 0)
source = "confirmed" if present else "computed"
```

A confirmed row only ever overrides its own definition's amount. An item subject to two definitions (e.g. foreign withholding + a local levy) resolves each independently — confirming one never affects the other. This mirrors the app's existing auto-derive pattern (`net_amount` derived from `gross_amount × fx_rate`; `total_value` derived from `quantity × unit_price`).

This mirrors the app's existing auto-derive pattern (gross/net from fx_rate, quantity/price/total from the other two): one field, either entered or derived.

**Note on write-time vs read-time**: Dividends' `taxable_base` is known at write time (gross amount), so confirmed tax could be auto-filled at creation. Sells' tax depends on FIFO cost basis + display-currency conversion + ruleset — all read-time. The form can still prefill an estimate for sells, but the authoritative number resolves at report time.

### Profile default ruleset (§17.13)

- `profiles.default_fiscal_rule TEXT` (nullable): user-override for the default ruleset.
- Null = locale-inferred (existing behavior: `es` → `spain`, `ja` → `japan`, else `default`).
- Non-null = user's explicit choice.
- Surfaced in Settings (read + edit) and on the Tax page header.

> **Implemented (write-time fallback)**: On transaction creation, the sell's or dividend's
> `fiscal_rule` snapshot is backfilled with `profiles.default_fiscal_rule` when no
> `fiscal_periods` match — the snapshot is never NULL when the profile has a default.
> The read-time effective ruleset still resolves via `rule_for_locale` (locale
> inference), not the profile default.
>
> **Originally designed (read-time override)**: The resolution order below was the
> original proposal. It was implemented as a write-time backfill only. The profile
> default does **not** affect the `ruleset` request parameter or an existing snapshot.

Original resolution order (not implemented): `fiscal_periods` (by date) → `profiles.default_fiscal_rule` → locale inference → `default`.

### Per-item detail (§17.12)

The `/analytics/taxable-pnl` response extends each fiscal year with an `items[]` list:

```python
class TaxablePnlItem(BaseModel):
    kind: Literal["sell", "dividend"]
    transaction_id: int
    instrument: str | None        # ticker / name
    date: date
    taxable_amount: float
    rule: str                     # frozen fiscal_rule
    tax_owed: float | None        # computed from brackets
    confirmed_tax: float | None   # from transaction_taxes
    source: Literal["computed", "confirmed"]
```

Items are sorted by date within each fiscal year.

### Tax page UX

#### Expandable year rows

Each fiscal year row is clickable to expand inline, showing:

```
▼ 2025  │ €72.00 gains │ €170.00 div │ €242.00 total │ €45.00 tax │ 1 sell │ 1 div
  ├─ SELL  AAPL      │ 2025-06-15 │ €72.00  │ spain (frozen) │ €13.68  │ computed
  └─ DIV   AAPL      │ 2025-08-01 │ €170.00 │ spain           │ €32.30  │ computed
```

Header row indicator shows the tax total (computed or confirmed).

#### Tax source badge

Each item's tax cell shows a badge: `computed` (derived from ruleset rate) or `confirmed` (user-entered). This is informational, not a separate column — one unified "Tax" value.

### Tax rates CRUD (Settings)

New Settings section "Tax Rates":

- Table: Ruleset | Category | From | To | Rate | Year | Edit | Delete.
- Add button opens `TaxRateModal` (ruleset dropdown, category dropdown, from/to inputs, rate input, year input).
- Full CRUD via `GET/POST/PUT/DELETE /tax-rates`.

## Response shape

### Extended `TaxablePnlFiscalYear`

```python
class TaxablePnlFiscalYear(BaseModel):
    fiscal_year: int
    start_date: date
    end_date: date
    realized_gains_taxable: float
    dividends_taxable: float
    total_taxable: float
    num_sells: int
    num_dividends: int
    # New in Phase 4:
    tax_owed: dict[str, float]           # {capital_gains: X, dividends: Y}
    total_tax_owed: float
    confirmed_tax: dict[str, float]      # from transaction_taxes
    total_confirmed_tax: float
    combined_base: float | None          # non-None when categories share a base
    items: list[TaxablePnlItem]
```

### Extended `TaxablePnlSummary`

```python
class TaxablePnlSummary(BaseModel):
    ruleset: str
    display_currency: str
    fiscal_years: list[TaxablePnlFiscalYear]
    total_taxable: float
    rate_fallbacks: list[PerformanceRateFallback]
    # New in Phase 4:
    default_ruleset: str                 # locale-inferred or profile override
```

## Files changed

### Backend

| File | Change |
|---|---|
| `backend/db/schema.sql` | Add `tax_rates` table; add `profiles.default_fiscal_rule` column |
| `backend/db/migrations/013_tax_rates.py` | New: table + column + seeded rates |
| `backend/db/queries.py` | `tax_rates` CRUD; `default_fiscal_rule` get/set |
| `backend/models/models.py` | `TaxRateCreate`, `TaxRateResponse`, `TaxablePnlItem`; extend `TaxablePnlFiscalYear`, `TaxablePnlSummary` |
| `backend/services/pnl_rules.py` | `TaxModel` protocol, `SavingsCombinedTaxModel`, `FlatPerCategoryTaxModel`, `TAX_CATEGORIES`, `TAX_MODELS`, `_apply_progressive` |
| `backend/services/tax_rate_svc.py` | New: CRUD delegation for tax rates |
| `backend/services/analytics_svc.py` | Extend `get_taxable_pnl`: tax_owed, confirmed_tax, items, combined_base, default_ruleset |
| `backend/routes/tax_rates.py` | New: `/tax-rates` CRUD endpoints |
| `backend/routes/analytics.py` | Register tax_rates router; extend response model |
| `backend/routes/profiles.py` | Expose `default_fiscal_rule` on profile endpoints |

### Frontend

| File | Change |
|---|---|
| `frontend/src/lib/api/analytics.js` | Add `taxRates` CRUD |
| `frontend/src/lib/components/TaxRateModal.svelte` | New: tax rate create/edit form |
| `frontend/src/routes/settings/+page.svelte` | New "Tax Rates" section + default ruleset display |
| `frontend/src/routes/tax/+page.svelte` | Expandable year rows, item detail, tax column with source badges |
| `frontend/src/lib/i18n/locales/en.ts` | `taxRates.*`, `tax.items.*`, `tax.source.*`, `fiscalRules.default` keys |
| `frontend/src/lib/i18n/locales/es.ts` | Spanish translations |

### Tests

| File | Change |
|---|---|
| `backend/tests/test_tax_models.py` | New: model computation tests (~30) |
| `backend/tests/test_tax_rates.py` | New: CRUD + seeding tests (~15) |
| `backend/tests/test_taxable_pnl.py` | Extended: tax_owed, confirmed, items, source (~10) |
| `backend/tests/test_fiscal_periods.py` | Extended: profile default, resolution chain (~3) |

### Docs

| File | Change |
|---|---|
| `doc/plans/tax_page.md` | This file (source-of-truth for the design) |
| `doc/plans/fiscal_rules_pnl_engine.md` | Add Phase 4 |
| `doc/calculations.md` | Expand §17 (§17.6–§17.13) |
| `doc/calculations_inventory.md` | Add Tax components |
| `doc/subsystems/database.md` | Add `tax_rates` table + `profiles.default_fiscal_rule` |
| `doc/subsystems/api_endpoints.md` | Add `/tax-rates` endpoints + extend `/taxable-pnl` |
| `doc/use_cases.md` | Add UC-49/50/51 |
| `doc/uc_9_planned.md` | Add UC-49/50/51 bodies |
| `doc/workflow.md` | Add tax rates CRUD + profile default workflow |
| `doc/uc_7_analytics_reads.md` | Update UC-48 notes |

## Out of scope

- Salary/work-income aggregation (abstraction designed for future addition).
- Progressive brackets that cross income categories (e.g. salary + savings in one bracket).
- Tax-rate import from external sources.
- CSV/PDF tax report export.
- Loss carry-forward across fiscal years.
- Category-aware fiscal exemptions (current model kept as-is).
