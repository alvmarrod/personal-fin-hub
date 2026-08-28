# Tier 1 — Foundation CRUD

Basic create, edit, and delete operations for reference entities. These are prerequisites for all other use cases.

---

## UC-01: Manage Entity

**Trigger**: User creates, edits, or deletes an entity (broker, bank, employer, exchange, other)

**Modeling decision**:

- Entity is an organizational container: name, entity_type, country, description
- No currency field — entities don't have a native currency. An entity (e.g., "Interactive Brokers") can hold accounts in multiple currencies, each tracked separately via transactions and balance snapshots
- Soft delete only (`deleted_at` timestamp). Hard delete never used.

**IF creating**:

- INSERT into `entities` with name, entity_type, country, description
- Duplicate `(name, entity_type)` for non-deleted rows → 409 Conflict

**IF editing**:

- UPDATE `entities` row. If `(name, entity_type)` changed, re-check uniqueness

**IF deleting (soft-delete)**:

- Pre-check: `SELECT 1 FROM transactions WHERE entity_id=? LIMIT 1` → if found, REJECT (409)
- Pre-check: `SELECT 1 FROM schedules WHERE entity_id=? LIMIT 1` → if found, REJECT (409)
- Pre-check: `SELECT 1 FROM balance_snapshots WHERE entity_id=? LIMIT 1` → if found, REJECT (409)
- If all clear: `UPDATE entities SET deleted_at=datetime('now') WHERE id=?`

**Rejected alternatives**:

- Hard delete → rejected: entity may be referenced by historical transactions that must be preserved for audit
- Cascading delete → rejected: would destroy transaction history

**Entities affected**: `entities` (write), `transactions` / `schedules` / `balance_snapshots` (read for pre-checks)

**UI pages**: Entities page (`/entities`)

**Constraints**:

- Entity type must be one of: BROKER, BANK, EMPLOYER, EXCHANGE, OTHER
- Soft-deleted entities are excluded from all queries except audit

---

## UC-02: Manage Market Asset

**Trigger**: User creates, edits, or deletes a market asset (stock, ETF, ETC, fund, etc.)

**Modeling decision**:

- Market asset represents a tradeable instrument with a fixed `market_code` (e.g., "AAPL", "ACX.MC", "CSPX.L")
- `currency_code` is the asset's native denomination — what the asset is priced in. This is the currency of the `prices` table entries and the `transactions.currency` when trading this asset
- Market asset is the link between external market data (prices, fundamentals) and the user's portfolio

**IF creating**:

- INSERT into `market_assets` with market_code, ticker, asset_type, asset_class, currency_code, name, description, exchange
- `currency_code` must exist in `currencies` table (FK constraint)
- Duplicate `market_code` → 409 Conflict
- `asset_type` must be one of: STOCK, ETF, ETC, FUND, INDEX FUND, CURRENCY, CRYPTO, OTHER
- `asset_class` is optional but must be one of: FI, VI, corp FI, Sovereign FI, mix FI, REIT, Gold, Monetary (if provided)

**IF editing**:

- UPDATE `market_assets` row. If `market_code` in body differs from path → 422

**IF deleting**:

- Pre-check: `SELECT 1 FROM portfolio_assets WHERE market_code=? LIMIT 1` → if found, REJECT (409)
- Pre-check: `SELECT 1 FROM prices WHERE market_code=? LIMIT 1` → if found, REJECT (409)
- If all clear: hard DELETE from `market_assets`

**Rejected alternatives**:

- Soft delete → rejected: market assets are reference data, not user-owned entities. If no portfolio asset references it, it should be fully removable
- Separating ticker from market_code → rejected: market_code IS the unique identifier, ticker is exchange-specific display

**Entities affected**: `market_assets` (write), `currencies` (read for FK validation), `portfolio_assets` / `prices` (read for pre-checks)

**UI pages**: Market Assets page (`/market-assets`)

**Constraints**:

- `currency_code` FK → `currencies(code)` must exist
- Market code is the primary key — immutable after creation

---

## UC-03: Manage Portfolio Asset

**Trigger**: User creates, edits, or deletes a portfolio asset

**Modeling decision**:

- Portfolio asset links a `market_asset` to the user's portfolio with investment-specific metadata
- No currency field — currency is inherited from `market_assets.currency_code`. This avoids duplication and ensures consistency: the asset's price, transaction currency, and valuation all use the same currency
- Portfolio asset is the unit of tracking: DCA status, layer (core/reserve/satellite), desired weight, TER, tracking mode

**IF creating**:

- INSERT into `portfolio_assets` with market_code, distribution_type, dca_status, layer, tactic, desired_weight, ter, tracking_mode, is_active, notes
- `market_code` must exist in `market_assets` (FK constraint)
- `tracking_mode` defaults to `auto`. If `manual`, the position's valuation comes from the `manual_values` snapshot ledger (see UC-45); `current_value_manual` is a legacy fallback column for pre-ledger data

**IF editing**:

- UPDATE `portfolio_assets` row
- Changing `is_active` to `false` closes the position (no new transactions should reference it, but historical ones remain)
- If `tracking_mode = manual` and the payload carries a manual value, the service ALSO upserts that value into `manual_values` with the requested `effective_date` (default today) — see UC-45. The frontend uses the same PUT endpoint for both modes; the backend resolves the ledger write internally, keeping the API transparent
- The `current_value_manual` column is kept in sync as a legacy fallback so pre-ledger data and fallback reads stay consistent

**IF deleting**:

- Pre-check: `SELECT 1 FROM transactions WHERE portfolio_asset_id=? LIMIT 1` → if found, REJECT (409)
- If all clear: hard DELETE from `portfolio_assets`

**Rejected alternatives**:

- Storing currency on portfolio_assets → rejected: would create a second source of truth conflicting with market_assets.currency_code
- Soft delete → rejected: portfolio assets are user-owned positions. If closed (is_active=false), they're inactive but still visible. Hard delete removes the position entirely.

**Entities affected**: `portfolio_assets` (write), `market_assets` (read for FK validation and currency inheritance), `transactions` (read for pre-checks)

**UI pages**: Portfolio Assets page (`/portfolio-assets`)

The page also renders each asset's per-buy breakdown as an expandable row (chevron → nested buy list with broker, category, quantity, unit price, total, currency) for assets with an open position — see `doc/subsystems/UI.md`.

**Constraints**:

- `market_code` FK → `market_assets(market_code)` must exist
- Currency is always derived: `SELECT currency_code FROM market_assets WHERE market_code = ?`

---

## UC-04: Record Price

**Trigger**: User or system records a market price for an asset at a point in time

**Modeling decision**:

- Price is always in the asset's native currency (inherited from `market_assets.currency_code`)
- No currency field on the `prices` table — the currency is implicit via the asset
- Unique constraint on `(market_code, timestamp)` — one price per asset per timestamp

**IF creating**:

- INSERT into `prices` with market_code, timestamp, price, provider
- `market_code` must exist in `market_assets` (FK constraint)
- Duplicate `(market_code, timestamp)` → 409 Conflict

**IF editing**:

- UPDATE `prices` row. Duplicate check applies.

**IF deleting**:

- Hard DELETE from `prices`. No pre-checks needed (prices have no dependents).

**Rejected alternatives**:

- Storing currency on prices → rejected: redundant with market_assets.currency_code. Would create risk of inconsistency
- Multiple prices per day → rejected: use the `provider` field to distinguish sources, but keep one price per timestamp per asset

**Entities affected**: `prices` (write), `market_assets` (read for FK validation and currency)

**UI pages**: Prices page (`/prices`)

**Constraints**:

- `market_code` FK → `market_assets(market_code)` must exist
- Price value is in the asset's native currency (from market_assets.currency_code)
- Unique `(market_code, timestamp)`

---

## UC-05: Manage Fiscal Exemption

**Trigger**: User creates, edits, or deletes a fiscal exemption rule

**Modeling decision**:

- Fiscal exemption represents a tax-advantaged wrapper (NISA, ISA, 401k, etc.)
- `exemption_amount` and `exemption_rate_limit` are currency-agnostic numbers — the currency context comes from the transaction that references this exemption
- `exemption_rate` is a percentage (0-100), not currency-dependent
- Exemption is linked to transactions via `transactions.fiscal_exemption_id`

**IF creating**:

- INSERT into `fiscal_exemptions` with exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit
- No FK constraints beyond the ID itself

**IF editing**:

- UPDATE `fiscal_exemptions` row

**IF deleting**:

- Pre-check: `SELECT 1 FROM transactions WHERE fiscal_exemption_id=? LIMIT 1` → if found, REJECT (409)
- If all clear: hard DELETE from `fiscal_exemptions`

**Rejected alternatives**:

- Adding a currency field to fiscal_exemptions → rejected: the same exemption (e.g., "NISA") may apply to transactions in different currencies. The currency context comes from the transaction, not the exemption rule
- Making exemption_amount currency-specific → rejected: would complicate multi-currency scenarios where the same NISA wrapper holds JPY and USD assets

**Entities affected**: `fiscal_exemptions` (write), `transactions` (read for pre-checks)

**UI pages**: Fiscal Exemptions page (`/fiscal-exemptions`)

**Constraints**:

- `exemption_rate` must be between 0 and 100
- `exemption_amount` ≥ 0
- Cannot delete if transactions reference this exemption

---

## UC-45: Record Manual Valuation

**Trigger**: User records or updates the current total value of a manual-tracked portfolio asset (`tracking_mode = manual`) at a point in time, or views/edits/deletes its valuation history

**Modeling decision**:

- A manual-tracked asset cannot be valued from market prices, so the user states its **total position value** at a point in time. This is a valuation snapshot, NOT a transaction: no cash moves and no quantity changes. Recording it as `INVESTMENT_BUY` would corrupt `net_quantity` and cost basis and is rejected
- The snapshot ledger is `manual_values`: `(portfolio_asset_id, value, effective_date)`, unique per `(portfolio_asset_id, effective_date)`. It is the manual-mode analog of UC-04's `prices` table and of `balance_snapshots` (an anchor value at a point in time)
- The asset's buy/sell activity is tracked independently in `transactions` (UC-08/UC-09, DCA contributions included). The two records are complementary: transactions evolve quantity and cost basis; `manual_values` statements the position's worth as of each date
- `value` is in the asset's native currency (inherited from `market_assets.currency_code`) — no currency field, mirroring `prices`
- All valuation reads (holdings, historical value, value chart) consume the ledger transparently, so the frontend does not need mode-specific read logic

**IF creating**:

- INSERT into `manual_values` with portfolio_asset_id, value, effective_date, notes
- `effective_date` defaults to today in the UI but is user-selectable (for backdated corrections), analogous to snapshot timestamps
- `portfolio_asset_id` must reference a manual-tracked portfolio asset (otherwise 422)
- Duplicate `(portfolio_asset_id, effective_date)` → the same-day entry is replaced (UPSERT), not duplicated. Revaluing twice on the same date corrects that day's snapshot

**IF editing**:

- UPDATE `manual_values` row (value / effective_date / notes)

**IF deleting**:

- Hard DELETE from `manual_values` (no dependents)

**UI write path**: The Portfolio Assets page exposes a single "current value" field whose save transparently upserts `manual_values` with the chosen `effective_date` (see UC-03 editing flow). The asset's valuation history (date · value · notes, with add/edit/delete) is shown in the asset detail area on the same page

**Rejected alternatives**:

- Recording the update as an `INVESTMENT_BUY` transaction → rejected: double-counts cost basis and inflates net_quantity. Buy transactions already exist independently and must not be conflated with valuations
- A single non-temporal `current_value_manual` column → rejected: overwrites history on every edit, which is the defect this UC fixes. The column is retained only as a legacy fallback for pre-migration rows
- Storing currency on `manual_values` → rejected: redundant with `market_assets.currency_code` (same reasoning as UC-04)

**Entities affected**: `manual_values` (write), `portfolio_assets` (read for tracking-mode validation), `market_assets` (read for currency)

**UI pages**: Portfolio Assets page (`/portfolio-assets`) — asset detail area

**Constraints**:

- `portfolio_asset_id` FK → `portfolio_assets(id)` must exist and be `tracking_mode = manual`
- `value` in the asset's native currency
- Unique `(portfolio_asset_id, effective_date)` — enforced via UPSERT, not error
