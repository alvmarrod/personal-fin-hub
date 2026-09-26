# Plan — Tax Definitions Engine

**Depends on**: Fiscal-Rules P&L Engine (`doc/plans/fiscal_rules_pnl_engine.md`), Tax Page (`doc/plans/tax_page.md`).
**Scope**: replace the hardcoded, per-ruleset `TaxModel` classes and the free-text `tax_type` vocabulary with a versioned data catalog, so new country-specific taxes, broker fees, and cross-border withholding can be added or corrected without new code branches.

## Problem

The current model conflates several distinct concerns into a small, hardcoded set of primitives:

- `TaxModel` (`SavingsCombinedTaxModel`, `FlatPerCategoryTaxModel`) hardcodes *both* how a ruleset's annual tax brackets combine *and* how a confirmed withholding tax interacts with the computed figure. Adding a new country, or a second tax within an existing country (e.g. Spain's capital-gains tax alongside its financial-transaction tax, "Tasa Tobin"), requires new code, not new data.
- `transaction_taxes.tax_type` is a small free-text/enum vocabulary (`capital_gains`, `dividends`, `withholding`, `stamp_duty`, `other`) with no link to a specific, nameable, versioned tax definition. The user cannot select "US foreign withholding" from a list — they type an amount and a category.
- Broker fees (`transaction_fees`) are recorded as bare amounts with no catalog to select from, even though the set of fee types a broker charges (buy commission, sell commission, FX commission) is small and repeats across transactions.
- There is no way to model that a single operation can be subject to more than one tax at once (e.g. a foreign bond purchase withheld at source *and* taxed locally) — today's model assumes one tax type per row with no structural link between related rows.

## Design decisions (confirmed)

1. **Two separate catalogs.** Country-level tax/levy definitions (state impositions: capital gains, dividends, Spain's Tasa Tobin, foreign withholding) and broker fee definitions (private commissions: buy/sell/FX commissions) are modeled as two independent tables. A tax is never a fee and vice versa, regardless of how either is labeled colloquially.

2. **No separate "taxable magnitude" per definition.** A `tax_definitions` row always computes automatically as `rate × the operation's own gross amount` (the transaction's own `total_value`/gross buy or sell amount) — never a derived net figure. If this formula doesn't fit a given tax in practice, the automatic figure is simply wrong, and the user corrects it by entering a confirmed amount — the same override mechanism used everywhere else (decision 7 below), not a special case requiring a richer formula.

3. **`rate = NULL` (or `0`) means "never auto-applies."** This is the entire mechanism for modeling taxes that must always be user-entered — foreign withholding, for instance, is not a special-cased concept; it is simply a `tax_definitions` row whose formula always yields zero until the user enters it manually. `broker_fee_definitions` follows the same naive principle with an even simpler shape: no rate, no formula, no default amount at all — pure catalog, always manual.

4. **Annual/combined-base taxation is modeled separately from per-operation definitions.** Spain's progressive "base del ahorro" (capital gains + dividends + interest share one bracket table) and Japan's flat per-category rate are both instances of `tax_bases`, replacing the `TaxModel` code classes with versioned data:
   - `tax_bases`: one row per ruleset (+ optional `year_start`), declares `computation` (`progressive` or `flat`) and, for flat, the rate directly.
   - `tax_base_categories`: which income categories (`capital_gains`, `dividends`, `interest`) feed a given base. Fixed per ruleset — not year-versioned.
   - `tax_base_rates`: bracket rows (`from_amount`, `to_amount`, `rate`), only present when `computation = 'progressive'`.

5. **Per-operation definitions link transactions directly, replacing free-text fields.** `transaction_taxes.tax_definition_id` (FK to `tax_definitions`) replaces the current `tax_type` string. `transaction_fees.broker_fee_definition_id` (FK to `broker_fee_definitions`) replaces free-text fee entries. No polymorphic association is needed — fees and taxes already live in separate tables, so each keeps its own single FK.

6. **`tax_definitions.slug` is a stable identity for formulas to reference.** A ruleset's `tax_bases` formula (e.g. Spain's) may need to find "the confirmed foreign-withholding row for this item" reliably — by a fixed slug (e.g. `foreign_withholding`), never by autoincrement `id` (meaningless across environments) or by translatable `name` (fragile). `broker_fee_definitions` needs no slug: no formula ever references a broker fee by identity, they are purely user-selectable amounts.

7. **Confirmed-vs-computed resolution stays uniform across every ruleset.** A confirmed row linked to a `tax_definitions` row replaces only the computed amount *for that specific definition* — never the item's total tax. If an operation is subject to two definitions (e.g. foreign withholding + local capital gains) and the user only confirms one, the other stays computed; they are resolved independently, not as a pair. "Crediting" a foreign withholding against Spain's savings-base tax is therefore not a resolution-layer behavior at all — it is a detail internal to Spain's own `tax_bases` formula, which reads the confirmed `foreign_withholding` row (by slug) as one of its own inputs, the same way it reads `bases`/`brackets` today.

8. **Foreign withholding is deducted at the whole `tax_bases` level, per year — never attributed back to individual items.** Mirrors Spain's real Art. 80 LIRPF mechanism (the tipo medio efectivo applies to the undecomposed savings base):

    ```text
    withholding = min(
        Σ confirmed transaction_taxes amounts on any generic (ruleset_key = NULL)
          tax_definitions row, for transactions whose fiscal_rule resolves to this
          tax_bases row's ruleset + year, converted to display_currency,
        total_tax
    )
    total_tax_owed = max(0, total_tax − withholding)
    ```

    Only applies when `computation = 'progressive'` — `computation = 'flat'` rulesets (Japan) keep today's full-substitution behavior for withholding, unaffected. `total_tax` is computed per decision 10 (chronological bracket attribution), not by a proportional split.

9. **Manually overriding the final combined `tax_owed` figure does not apply.** The user can still correct any individual confirmed `transaction_taxes` row (§17.11, unchanged) — including their own withholding — but cannot force the year's *combined*, post-withholding total to an arbitrary number. The withholding formula in decision 8 is the only way a confirmed row influences `tax_owed`. A separate retained-vs-computed comparison view (tracked separately) lets the user see any mismatch, but never lets them substitute the combined figure directly.

10. **Within a `computation = 'progressive'` tax_bases row, each item's own tax is attributed by chronological bracket order — not a proportional split.** Items (sells, dividends, interest) sharing that base for the fiscal year are ordered by `timestamp` ascending; as each item's `taxable_amount` is added to a running total, the portion of it that falls within each bracket is taxed at that bracket's rate (an item can span 2+ brackets). `tax_owed[category]` is the bottom-up sum of its items' own attributed tax, not `total_tax × (bases[category] / combined_base)`. Sub-day timestamp resolution makes exact ties practically impossible, so no separate tie-break key is defined. This is computed at read time — nothing is stored, so a later-inserted past-dated transaction shifts every subsequent item's bracket position on the next read. See §17.9 for the full formula.

## Schema

```sql
CREATE TABLE tax_bases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruleset_key TEXT NOT NULL,
    name TEXT NOT NULL,
    computation TEXT NOT NULL CHECK (computation IN ('progressive', 'flat')),
    flat_rate REAL,              -- only when computation = 'flat'
    year_start INTEGER           -- NULL = default for all years
);

CREATE TABLE tax_base_categories (
    tax_base_id INTEGER NOT NULL REFERENCES tax_bases(id),
    category TEXT NOT NULL CHECK (category IN ('capital_gains', 'dividends', 'interest')),
    PRIMARY KEY (tax_base_id, category)
    -- Fixed per ruleset — no year_start here (decision: keep this mapping non-versioned for now).
);

CREATE TABLE tax_base_rates (       -- only present when the parent's computation = 'progressive'
    tax_base_id INTEGER NOT NULL REFERENCES tax_bases(id),
    from_amount REAL NOT NULL,
    to_amount REAL,               -- NULL = unbounded top bracket
    rate REAL NOT NULL
);

CREATE TABLE tax_definitions (       -- per-operation taxes/levies (state impositions)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,     -- stable reference for tax_bases formulas, e.g. 'foreign_withholding'
    ruleset_key TEXT,              -- NULL = generic, not tied to one country (e.g. foreign withholding)
    name TEXT NOT NULL,
    rate REAL,                     -- NULL/0 = never auto-applies; user must enter a confirmed amount
    year_start INTEGER
);

CREATE TABLE broker_fee_definitions (  -- pure catalog, no formula
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- Existing tables, extended:
ALTER TABLE transaction_taxes ADD COLUMN tax_definition_id INTEGER REFERENCES tax_definitions(id);
-- tax_type (free-text) is superseded by tax_definition_id and removed once the migration completes.

ALTER TABLE transaction_fees ADD COLUMN broker_fee_definition_id INTEGER REFERENCES broker_fee_definitions(id);
```

### Worked example (Spain / Japan), illustrating decisions 1–4

| Table | Spain | Japan |
|---|---|---|
| `tax_bases` | `name="IRPF sobre el ahorro"`, `computation='progressive'` | `name="Impuesto de capitales"`, `computation='flat'`, `flat_rate=<value TBD>` |
| `tax_base_categories` | `capital_gains`, `dividends`, `interest` → same base | `capital_gains`, `dividends`, `interest` → same base |
| `tax_base_rates` | N ascending brackets (`from_amount`/`to_amount`/`rate` rows — exact values TBD at seeding) | — (flat, no brackets) |
| `tax_definitions` | `slug='spain_itf'`, `ruleset_key='spain'`, `name="Tasa Tobin"`, `rate=<value TBD>` | — (none beyond the generic ones below) |
| `tax_definitions` (generic) | `slug='foreign_withholding'`, `ruleset_key=NULL`, `rate=NULL` — usable by any ruleset's formula, always user-entered | same row, referenced by Japan's formula too |

A US-sourced interest payment while Japan is the active ruleset is not modeled as part of `tax_bases` at all — it is a `foreign_withholding` `tax_definitions` row on that one transaction, confirmed manually, exactly as Tasa Tobin is on a Spanish purchase.

## Out of scope

- The specific list of seed rows for Spain, Japan, and broker fee definitions (tracked separately, once this schema is applied).
- Any country's tax model beyond Spain and Japan.
- A review of the current codebase against this design, and the migration that introduces these tables (tracked separately, once the schema above is applied).
