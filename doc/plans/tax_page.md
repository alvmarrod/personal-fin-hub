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

### TaxModel abstraction (§17.7)

Tax computation is split into two layers:

- **Model structure** (code): a per-ruleset `TaxModel` that defines how categories combine, whether brackets are progressive, and how exemptions reduce the base. Finite registry, matches the `PnlRule` pattern.
- **Tax parameters** (data): rates, brackets, thresholds — user-editable, stored in a `tax_rates` table, changing by year/country.

This keeps "how to compute" in code (extensible by adding a new model type) and "what rates to use" in data (user-configurable, no code change for rate adjustments).

#### v1 models

| Model type | Ruleset(s) | Behavior |
|---|---|---|
| `SavingsCombined` | `spain`, `default` | Gains + dividends share one progressive bracket table (Spain "savings income"). Combined base = sum of post-exemption category bases; tax computed on combined total; split proportionally back to categories. |
| `FlatPerCategory` | `japan`, `latest`, `none` | Flat rate per category, no combining. Each category taxed independently. |

Adding a new country = choose a model type + insert rate rows.

### Tax categories (§17.6)

Extensible enum of taxable income types:

| Category | v1 status | Notes |
|---|---|---|
| `capital_gains` | Implemented | Realized gains from sells. |
| `dividends` | Implemented | Dividend income. |
| `salary` | Reserved | Future: work-income aggregation. |
| `interest` | Reserved | Future: interest income. |
| `other` | Reserved | Future: catch-all. |

### Tax rates as data (§17.8)

The `tax_rates` table stores brackets/rates per ruleset, category, and year:

```sql
CREATE TABLE tax_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruleset_key TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('capital_gains', 'dividends')),
    from_amount REAL NOT NULL DEFAULT 0,
    to_amount REAL,          -- NULL = unbounded top bracket
    rate REAL NOT NULL,      -- fraction (e.g. 0.19 = 19%)
    year_start INTEGER,      -- tax year these apply to; NULL = default
    profile_id INTEGER REFERENCES profiles(id)
);
```

- **Flat rate**: one row per category (`from_amount=0, to_amount=NULL`).
- **Progressive brackets**: multiple rows per category with ascending `from_amount` bands, each with its own `rate`.
- **Year-specific**: `year_start` allows different rates per tax year; NULL = fallback for all years.
- **Profile-scoped**: optional `profile_id` for per-profile overrides.

#### Seeded data (migration 013)

| Ruleset | Category | Brackets |
|---|---|---|
| `spain` | `capital_gains` | Progressive: 19% (€0–6k), 21% (€6k–50k), 23% (€50k+) |
| `spain` | `dividends` | Same progressive bands (shared "savings income" base) |
| `japan` | `capital_gains` | Flat 20.315% |
| `japan` | `dividends` | Flat 20.315% |
| `default` | `capital_gains` | Copy of Spain |
| `default` | `dividends` | Copy of Spain |
| `latest` / `none` | — | No rates seeded (no tax computed) |

### Computed tax (§17.9)

Per fiscal year, the engine:

1. Collects `bases[category]` = post-exemption taxable base (already computed by Phase 3).
2. Loads brackets from `tax_rates` for the resolved ruleset + year.
3. Selects the `TaxModel` from the `TAX_MODELS` registry.
4. Calls `model.compute(bases, brackets)` → `TaxResult { tax_owed, total_tax_owed, combined_base }`.

#### SavingsCombined (Spain)

```text
combined_base = bases[capital_gains] + bases[dividends]
total_tax = apply_progressive(combined_base, brackets)
tax_owed[category] = total_tax × (bases[category] / combined_base)   # proportional split
```

If `combined_base = 0`, all `tax_owed` are 0.

#### FlatPerCategory (Japan)

```text
tax_owed[category] = bases[category] × brackets[category].rate
total_tax_owed = sum(tax_owed)
```

### Confirmed tax (§17.10)

Confirmed (actual) tax is stored per transaction in `transaction_taxes`:

- `tax_type` formalized vocabulary: `capital_gains`, `dividends`, `withholding`, `stamp_duty`, `other`.
- `tax_amount` = the user-entered amount.
- Aggregated per category + per fiscal year from the transaction's date.

### Tax resolution (§17.11)

Per item, one value:

```text
tax = confirmed_tax if present else computed_tax
source = "confirmed" if present else "computed"
```

This mirrors the app's existing auto-derive pattern (gross/net from fx_rate, quantity/price/total from the other two): one field, either entered or derived.

**Note on write-time vs read-time**: Dividends' `taxable_base` is known at write time (gross amount), so confirmed tax could be auto-filled at creation. Sells' tax depends on FIFO cost basis + display-currency conversion + ruleset — all read-time. The form can still prefill an estimate for sells, but the authoritative number resolves at report time.

### Profile default ruleset (§17.13)

- `profiles.default_fiscal_rule TEXT` (nullable): user-override for the default ruleset.
- Null = locale-inferred (existing behavior: `es` → `spain`, `ja` → `japan`, else `default`).
- Non-null = user's explicit choice.
- Surfaced in Settings (read + edit) and on the Tax page header.

> **Implemented (write-time fallback)**: On transaction creation, the sell's `fiscal_rule`
> snapshot is backfilled with `profiles.default_fiscal_rule` when no `fiscal_periods`
> match — the snapshot is never NULL when the profile has a default. The read-time
> effective ruleset still resolves via `rule_for_locale` (locale inference), not the
> profile default.
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
