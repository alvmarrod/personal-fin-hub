# View: Tax (`/tax`) + Fiscal Settings

> Taxable P&L per fiscal year and the Settings sections that drive it. Component/design conventions live in `doc/subsystems/UI.md`; calculation semantics in `doc/calculations.md` §16–§17; use cases UC-47–UC-50; plan of record `doc/plans/tax_page.md`.

## Tax Page Layout

```text
+----------------------------------------------------------+
| [☰]  Tax              [Ruleset ▾] [USD ▾]                 |  ← Ruleset + display currency selectors
+------------+---------------------------------------------+
|            |  ⚠ Rate fallback warning (conditional)       |
|            |  ┌──────────────────────────────┐            |
| Tax        |  │ Fiscal-year table             │            |  ← One row per fiscal year
|            |  │ ▶ 2025 ... (expandable)       │            |  ← Expand → per-item detail
|            |  └──────────────────────────────┘            |
|            |  Totals footer                               |
+------------+---------------------------------------------+
```

## Selectors

- **Ruleset** (`spain` / `japan` / `default` / `latest` / `none`): drives both the sell-conversion rules and the fiscal-year start; defaults to the locale-derived rule (`tax.ruleset` placeholder). Changing it reloads the data.
- **Display currency**: shared preference selector; converts all amounts.

## Fiscal-Year Table

One row per fiscal year with columns:

| Column | Content |
|--------|---------|
| Fiscal Year | Expand/collapse toggle (▶/▼) |
| Realized Gains | Taxable gains total (green/red) |
| Dividends | Taxable dividends total (green/red) |
| Total | Combined taxable base |
| Tax Owed | Per-category breakdown rows when the model combines categories (e.g. Spain `SavingsCombined`), single value for flat models |
| Sells / Dividends | Item counts |

**Expanded year — per-item table:**

| Column | Content |
|--------|---------|
| Date | Item date (`YYYY-MM-DD`) |
| Tax Ruleset | Localized ruleset applied to the row (frozen `fiscal_rule` for sells, per-date resolved rule for dividends) |
| Asset | Ticker, market code, entity name, or `#transaction_id` fallback |
| Category | Localized (`capital_gains`, `dividends`) |
| Native Amount | Gross amount in the item's original currency |
| Display Amount | Plain FX conversion of the native amount at the transaction date (§16.4) |
| Tax Exemption | Linked exemption policy name (e.g. `NISA`) when the row is exempt from tax, else `—` |
| Taxable Amount | Rule-converted (§16.2) then exemption-reduced (§17.4) base in display currency |
| Tax Owed | Computed per item from the ruleset brackets |
| Source | Badge: **Confirmed** (from `transaction_taxes`) vs computed |

## Rate-Fallback Warning

Same callout pattern as the Performance page: rendered when the response's `rate_fallbacks` is non-empty (`tax.rateFallbackTitle` / `rateFallbackMsg`).

## API Dependencies

| Endpoint | Purpose |
|----------|---------|
| `GET /analytics/taxable-pnl-extended?display_currency=&locale=&ruleset=` | Fiscal years + per-line items, tax owed, confirmed-vs-computed sources, per-category breakdown |
| `GET /currencies` | Display-currency selector options |

---

## Related Settings Sections (`/settings`)

### Fiscal Rules (periods)

- Lists profile-scoped periods as `rule name` + `start_date — end_date` (or "open ended"), with Edit/Delete actions and an **Add** button opening `FiscalPeriodModal`.
- A period assigns a rule (`Spain` / `Japan` / `Default` / `Legacy` / `No rule`) to a date range. The backend resolves each sell's rule from the period covering its sell date and freezes it onto the transaction; overlapping ranges are rejected (422).
- Empty state text when no periods exist (all sells fall back to the locale-inferred default).

### Default Ruleset

- Single selector persisting `profiles.default_fiscal_rule`. Empty = locale-inferred default (hint shown only when an explicit override is set).

### Tax Rates

- CRUD list over the `tax_rates` table: rows render as `Ruleset — Category` with the bracket `{from_amount} — {to_amount | unlimited}: rate% (year+)`.
- **Add/Edit** opens `TaxRateModal` (ruleset, category, amount band, rate, optional `year_start`); flat rates are a single `0 → ∞` row, progressive models use ascending bands. Delete goes through the confirm modal.
- Seeded defaults: Spain progressive savings rates, Japan flat per-category rates.

## API Dependencies (Settings)

| Endpoint | Purpose |
|----------|---------|
| `GET/POST/PUT/DELETE /fiscal-periods` | Fiscal rule periods CRUD (overlap-rejecting) |
| `PUT /profiles/{id}` | Persist `default_fiscal_rule` |
| `GET/POST/PUT/DELETE /tax-rates` | Tax bracket CRUD |
