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
| `spain`, `default` | `progressive` | Gains + dividends + interest share one progressive bracket table (Spain "savings income"). Combined base = sum of post-exemption category bases; tax computed per item as the base fills brackets in chronological order (decision 10). |
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

#### `computation = 'progressive'` (Spain)

Items (sells, dividends, interest) are ordered by `timestamp` ascending within the fiscal year; each item's own bracket share is computed by where it falls as brackets fill up. Sub-day timestamp resolution makes exact ties practically impossible — no separate tie-break key is needed.

```text
  running_total = 0
  for item in items sorted by timestamp ascending:
      item_tax_owed = apply_progressive(running_total → running_total + item.taxable_amount, tax_base_rates)
      running_total += item.taxable_amount
      # item_tax_owed may span 2+ brackets

  tax_owed[category] = Σ item_tax_owed of that category's items   # bottom-up, not a proportional split
  total_tax           = Σ tax_owed[category]

  withholding = min(
      Σ confirmed transaction_taxes amounts on any generic (ruleset_key = NULL)
        tax_definitions row, for transactions whose fiscal_rule resolves to this
        tax_bases row's ruleset + year, converted to display_currency,
      total_tax
  )
  total_tax_owed = max(0, total_tax − withholding)
```

`withholding`/`total_tax_owed` exist only at the year level — `item_tax_owed` is never reduced by `withholding`. If there are no items, all `tax_owed` are 0. This is computed at read time like the rest of `tax_owed` — nothing is stored or overwritten; a later-inserted past-dated transaction shifts every subsequent item's bracket position on the next read.

`apply_progressive(range, tax_base_rates)` walks brackets in ascending `from_amount` order: for each bracket, the portion of the range within `[from_amount, to_amount)` is taxed at that bracket's `rate`.

#### `computation = 'flat'` (Japan)

```text
tax_owed[category] = bases[category] × tax_bases.flat_rate
total_tax_owed = Σ tax_owed[category]
```

### Confirmed tax (§17.10)

Confirmed (actual) tax is stored per transaction in `transaction_taxes`, each row linked to a `tax_definitions` row via `tax_definition_id` (replaces the old `tax_type` free-text vocabulary):

- `tax_amount` = the user-entered amount, specific to that one `tax_definitions` row on that one transaction.
- Resolved per item, per definition — see §17.11. Not aggregated per category across the whole fiscal year the way the old `tax_type` vocabulary was.

Overriding the final combined `tax_owed` figure does not apply — see decision 9 in `doc/plans/tax_definitions_engine.md` for the rationale. A confirmed row linked to a generic (`ruleset_key = NULL`) `tax_definitions` row also feeds the §17.9 withholding in `computation = 'progressive'` rulesets.

### Tax resolution (§17.11)

Per `tax_definitions`-linked row on an item — not per item as a whole:

```text
computed  = rate × gross, if tax_definitions.rate is set, else 0
confirmed = the transaction_taxes amount for this tax_definition_id, if a row exists, else null
```

A confirmed row only ever overrides its own definition's amount. An item subject to two definitions (e.g. foreign withholding + a local levy) resolves each independently — confirming one never affects the other. This mirrors the app's existing auto-derive pattern (`net_amount` derived from `gross_amount × fx_rate`; `total_value` derived from `quantity × unit_price`).

A confirmed row can serve two roles at once: it resolves its own line per the formula above, and — only when it is a generic (`ruleset_key = NULL`) withholding-type row on a `computation = 'progressive'` ruleset — it also feeds the §17.9 withholding total.

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

The `/analytics/taxable-pnl` response extends each fiscal year with an `items[]` list. Field set reconciled with `calculations/finance.md` §17.12 (the two had diverged — this is now the single source of truth for both):

```python
class TaxablePnlItemTax(BaseModel):
    tax_definition_id: int
    slug: str                     # tax_definitions.slug
    name: str                     # tax_definitions.name
    computed: float                # rate × native_amount if tax_definitions.rate is set and applies to this item's ruleset; always 0 for a naive (rate NULL/0) definition
    confirmed: float | None        # matching transaction_taxes amount for this definition, None if not entered

class TaxablePnlItem(BaseModel):
    transaction_id: int
    market_code: str | None
    ticker: str | None
    name: str | None
    category: Literal["capital_gains", "dividends"]
    date: date
    native_amount: float
    display_amount: float
    taxable_amount: float
    tax_owed: float | None        # this item's own bracket-attributed tax (decision 10); None if no rates configured
    fiscal_rule: str | None
    tax_policy: str | None
    currency: str
    taxes: list[TaxablePnlItemTax]
```

`taxes` inclusion rule — a `tax_definitions` row appears for an item when either:
(a) it auto-applies (`rate` set, `ruleset_key` matches the item's ruleset or is generic/NULL): `computed = rate × native_amount`, `confirmed` = the matching `transaction_taxes` amount if one exists, else `None`; or
(b) it is naive (`rate` NULL/0) but a confirmed `transaction_taxes` row exists linking this transaction to this definition: `computed = 0`, `confirmed` = that amount.
A naive definition with no confirmed row for this item never appears in `taxes`.

Items are sorted by date within each fiscal year.

### Tax page UX

#### Expandable year rows

Each fiscal year row is clickable to expand inline, showing:

```
▼ 2025  │ €72.00 gains │ €170.00 div │ €242.00 total │ €45.00 tax │ 1 sell │ 1 div
  ├─ SELL  AAPL      │ 2025-06-15 │ €72.00  │ spain (frozen) │ €13.68  │ 1 tax
  └─ DIV   AAPL      │ 2025-08-01 │ €170.00 │ spain           │ €32.30  │ 2 taxes
```

Header row indicator shows the tax total (`tax_owed`, summed with each item's confirmed amounts where present per §17.11's resolution). The rightmost item column now shows a tax count, not a single value+badge.

#### Per-item tax breakdown

Expanding an item row further shows one line per entry in its `taxes[]` list:

```
      └─ Tasa Tobin           computed €0.14   confirmed —
      └─ Foreign withholding  computed —       confirmed €12.00
```

Each line shows the definition's `name`, its `computed` amount (always shown, `—` only has no meaning since it is always a number — 0 for a naive definition with no confirmed override), and its `confirmed` amount (`—` when not entered). This replaces the single computed-or-confirmed badge: an item can now show one entry fully computed, another fully confirmed, and a third with both — since each definition resolves independently (§17.11).

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
    tax_owed: dict[str, float]           # {capital_gains: X, dividends: Y, interest: Z}
    total_tax_owed: float
    confirmed: dict[str, float]         # from transaction_taxes, mirrors tax_owed's shape
    total_confirmed: float
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
| `backend/services/analytics_svc.py` | Extend `get_taxable_pnl`: tax_owed, taxes, items, combined_base, default_ruleset |
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
| `doc/calculations/finance.md` | Expand §17 (§17.6–§17.13) |
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
