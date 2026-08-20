# Subsystem: Database

## Backups

The database is automatically backed up daily, around migrations, and on demand.
Backups use the stdlib `sqlite3.Connection.backup()` API (consistent under
concurrent writes), are verified after creation, and pruned to `BACKUP_RETENTION`
newest files. See `doc/subsystems/backups.md` for the full design, env config
(`BACKUP_ENABLED`/`BACKUP_DIR`/`BACKUP_TIMEZONE`/`BACKUP_CRON`/`BACKUP_RETENTION`),
and restore procedure.

## Schema Source

`backend/db/schema.sql`

## Tables

### profiles

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL, UNIQUE |
| `password_hash` | TEXT | NULL = passwordless profile |
| `default_fiscal_rule` | TEXT | NULL = locale-inferred; non-null = user override for the default ruleset |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) |

Every user-created table below carries a `profile_id INTEGER REFERENCES profiles(id)` column scoping its rows to a profile. Market reference data (`currencies`, `market_assets`, `prices`, `stock_splits`) and `scheduler_state` are shared and intentionally not profile-scoped.

### market_assets

| Column | Type | Constraints |
|--------|------|-------------|
| `market_code` | TEXT | PRIMARY KEY |
| `ticker` | TEXT | Exchange-specific (e.g., "AAPL.US", "TEF.MC") |
| `asset_type` | TEXT | NOT NULL, CHECK (STOCK, ETF, ETC, FUND, INDEX FUND, CURRENCY, CRYPTO, OTHER) |
| `asset_class` | TEXT | CHECK (FI, VI, corp FI, Sovereign FI, mix FI, REIT, Gold, Monetary) |
| `currency_code` | TEXT | REFERENCES currencies(code) |
| `name` | TEXT | |
| `description` | TEXT | |
| `exchange` | TEXT | |
| `last_synced_at` | DATETIME | Last successful market-API fetch for this code (price-sync freshness skip) |

### portfolio_assets

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `market_code` | TEXT | NOT NULL, REFERENCES market_assets(market_code) |
| `distribution_type` | TEXT | CHECK (accumulation, distribution, N/A) |
| `dca_status` | TEXT | CHECK (ongoing, paused, closed) |
| `layer` | TEXT | CHECK (core, reserve, satellite) |
| `tactic` | BOOLEAN | DEFAULT FALSE |
| `desired_weight` | REAL | Target weight 0-100% |
| `ter` | REAL | Total Expense Ratio (e.g., 0.5 = 0.5%) |
| `tracking_mode` | TEXT | CHECK (auto, manual), DEFAULT 'auto' |
| `current_value_manual` | REAL | **Legacy** fallback valuation. Source of truth is the `manual_values` ledger (UC-45); kept in sync on writes for pre-ledger data |
| `is_active` | BOOLEAN | DEFAULT TRUE |
| `closing_date` | DATE | |
| `notes` | TEXT | |

### transactions

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `timestamp` | DATETIME | NOT NULL |
| `type` | TEXT | NOT NULL, CHECK (INCOME, MONEY_OUT, INVESTMENT_BUY, INVESTMENT_SELL, TRANSFER, TRANSFER_IN, TRANSFER_OUT, BALANCE_ADJUSTMENT) |
| `investment_transaction_category` | TEXT | CHECK (NORMAL, DCA, REBALANCE). Investment-only; only set for `type = INVESTMENT_BUY/INVESTMENT_SELL` |
| `income_category` | TEXT | CHECK (salary, other, dividends, interest, cashback). Strict subclassification of `INCOME` transactions; drives the Income page category chart. Only set for `type = INCOME`. Null falls back to entity derivation in analytics |
| `entity_id` | INTEGER | NOT NULL, REFERENCES entities(id) |
| `portfolio_asset_id` | INTEGER | REFERENCES portfolio_assets(id) |
| `quantity` | REAL | |
| `unit_price` | REAL | |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |
| `total_value` | REAL | Computed by service layer (quantity * unit_price if not provided) |
| `gross_amount` | REAL | Before fees and tax |
| `net_amount` | REAL | After fees and tax |
| `payment_currency` | TEXT | REFERENCES currencies(code) |
| `fx_rate` | REAL | 1 currency = X payment_currency |
| `settlement_date` | DATE | |
| `fiscal_exemption_id` | INTEGER | References fiscal_exemptions(id) |
| `fiscal_rule` | TEXT | Rule key (`spain`/`japan`/`default`/`latest`/`none`) active on the sell date, snapshotted at creation for `INVESTMENT_SELL`. Guarantees past operations are never recomputed when fiscal periods change. NULL = no period matched (read-time locale fallback). |
| `dividend_type` | TEXT | CHECK (regular, special, qualified); only meaningful when `income_category='dividends'` |
| `record_date` | DATE | Dividend eligibility date; only meaningful when `income_category='dividends'` |
| `payment_date` | DATE | Dividend payment date; only meaningful when `income_category='dividends'` |
| `dividend_currency` | TEXT | Original dividend currency; only meaningful when `income_category='dividends'` |
| `dividend_payment_currency` | TEXT | Currency received; only meaningful when `income_category='dividends'` |
| `dividend_fx_rate` | REAL | 1 dividend_currency = X payment_currency; only meaningful when `income_category='dividends'` |
| `notes` | TEXT | User annotation |

### transaction_fees

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `transaction_id` | INTEGER | NOT NULL, REFERENCES transactions(id) |
| `fee_type` | TEXT | NOT NULL, CHECK (BROKER, FX, PLATFORM, OTHER) |
| `nature` | TEXT | NOT NULL, CHECK (FIXED, PERCENTAGE, BOTH, MIN) |
| `fixed_amount` | REAL | DEFAULT 0.0 |
| `percentage` | REAL | DEFAULT 0.0 |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |

### transaction_taxes

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `transaction_id` | INTEGER | NOT NULL, REFERENCES transactions(id) |
| `tax_type` | TEXT | NOT NULL (e.g., WITHHOLDING, STAMP_DUTY, VAT, CAPITAL_GAINS) |
| `tax_rate` | REAL | |
| `tax_amount` | REAL | |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |

### schedules

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `description` | TEXT | NOT NULL |
| `start_date` | DATE | NOT NULL |
| `end_date` | DATE | |
| `periodicity_type` | TEXT | NOT NULL, CHECK (ONE_OFF, DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY, CUSTOM) |
| `custom_cron` | TEXT | |
| `linked_transaction_id` | INTEGER | REFERENCES transactions(id) |
| `entity_id` | INTEGER | REFERENCES entities(id) |
| `currency` | TEXT | REFERENCES currencies(code) |
| `type` | TEXT | Transaction type for materialized transactions |
| `income_category` | TEXT | CHECK (salary, other, dividends, interest, cashback). Optional; copied onto every materialized transaction |
| `total_value` | REAL | Amount per occurrence |
| `notes` | TEXT | |

> **Note on `linked_transaction_id`:** This column exists in the schema but is **currently unused**. The schedule materialization logic (scheduler/scheduler.py) reads embedded fields (`entity_id`, `currency`, `type`, `total_value`, `notes`) directly from the schedule row and creates a new transaction from scratch. The `linked_transaction_id` column was designed for a previous iteration where schedules would copy a template transaction. It is retained in the schema for potential future use (e.g., tracking which transaction originally inspired a schedule) but no code currently reads or writes it.

### schedule_occurrences

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `schedule_id` | INTEGER | NOT NULL, REFERENCES schedules(id) |
| `occurrence_date` | TEXT | NOT NULL |
| `transaction_id` | INTEGER | NOT NULL, REFERENCES transactions(id) |
| UNIQUE | (schedule_id, occurrence_date) | |

Each row records that `schedule_id` fired for `occurrence_date` and produced `transaction_id`. The scheduler checks this table **before** creating any materialized transaction — if a row exists, the fire is skipped. This survives manual edits to the transaction's timestamp, amount, or notes because the occurrence record is never modified by the user.

The `[schedule:N]` tag in `transactions.notes` becomes optional — it is kept as a convenience label but is no longer used for deduplication.

### balance_snapshots

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `entity_id` | INTEGER | NOT NULL, REFERENCES entities(id) |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |
| `amount` | REAL | NOT NULL |
| `timestamp` | DATETIME | NOT NULL |
| `notes` | TEXT | |

### manual_values

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `portfolio_asset_id` | INTEGER | NOT NULL, REFERENCES portfolio_assets(id) |
| `value` | REAL | NOT NULL — total position value |
| `effective_date` | DATE | NOT NULL |
| `recorded_at` | DATETIME | NOT NULL DEFAULT now |
| `notes` | TEXT | |
| UNIQUE | (portfolio_asset_id, effective_date) | Upserted, never duplicated |

Time-series snapshot ledger for manual-tracked assets (UC-45). Each row states the **total position value** of a `tracking_mode = manual` asset as of `effective_date` — the manual-mode analog of `prices` (for auto assets) and `balance_snapshots` (for cash). Value is in the asset's native currency (inherited from `market_assets.currency_code`). Buy/sell activity is tracked separately in `transactions`; the ledger only records valuations. Revaluing on a date that already has a snapshot replaces that date's row (UPSERT).

### currencies

| Column | Type | Constraints |
|--------|------|-------------|
| `code` | TEXT | NOT NULL |
| `base_code` | TEXT | NOT NULL |
| `rate` | REAL | NOT NULL |
| `timestamp` | DATETIME | NOT NULL |
| PRIMARY KEY | (code, base_code, timestamp) |

### prices

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `market_code` | TEXT | NOT NULL, REFERENCES market_assets(market_code) |
| `timestamp` | DATETIME | NOT NULL |
| `price` | REAL | NOT NULL |
| `provider` | TEXT | |

### entities

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `entity_type` | TEXT | NOT NULL, CHECK (BROKER, BANK, EMPLOYER, EXCHANGE, OTHER) |
| `country` | TEXT | |
| `description` | TEXT | |
| `deleted_at` | DATETIME | DEFAULT NULL |

### fiscal_exemptions

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `exemption_type` | TEXT | NOT NULL (e.g., NISA, ISA, 401k) |
| `description` | TEXT | |
| `exemption_amount` | REAL | DEFAULT 0 |
| `exemption_rate` | REAL | DEFAULT 100 (100%) |
| `exemption_rate_limit` | REAL | NULL = no limit |

### fiscal_periods

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `profile_id` | INTEGER | REFERENCES profiles(id) |
| `rule_key` | TEXT | NOT NULL — one of the PnlRule registry keys (`spain`, `japan`, `default`, `latest`, `none`) |
| `start_date` | DATE | NOT NULL |
| `end_date` | DATE | NULL = open-ended (no end) |

Assigns a fiscal rule to a date range for a profile. The rule governing an operation is the period containing its **sell date**; resolved and frozen onto the transaction at creation (`transactions.fiscal_rule`). No match → locale-inferred default rule (fallback `default`). `rule_key = 'none'` means "no rule" and converts identically to `default`. Overlapping periods within a profile are rejected. See UC-47.

### tax_rates

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `ruleset_key` | TEXT | NOT NULL — one of the PnlRule registry keys |
| `category` | TEXT | NOT NULL, CHECK (`capital_gains`, `dividends`) |
| `from_amount` | REAL | NOT NULL DEFAULT 0 — lower bound of bracket |
| `to_amount` | REAL | NULL = unbounded top bracket |
| `rate` | REAL | NOT NULL — fraction (e.g. 0.19 = 19%) |
| `year_start` | INTEGER | NULL = default/fallback for all years |
| `profile_id` | INTEGER | REFERENCES profiles(id) — per-profile rate overrides |

Stores tax brackets/rates per ruleset, category, and year. Flat rate = one row per category (`from_amount=0,`to_amount=NULL`). Progressive brackets = multiple rows with ascending`from_amount` bands. Seeded per ruleset in migration 013; user-editable via Settings CRUD. See UC-49, `calculations.md` §17.8.

## Relationships

- portfolio_assets (many) → market_assets (one)
- transactions (many) → portfolio_assets (one) via portfolio_asset_id
- transactions (many) → entities (one)
- transactions (many) → fiscal_exemptions (one)
- transaction_fees (many) → transactions (one)
- transaction_taxes (many) → transactions (one)
- prices (many) → market_assets (one)
- manual_values (many) → portfolio_assets (one) via portfolio_asset_id
- balance_snapshots (many) → entities (one)
- balance_snapshots (many) → currencies (one)
- fiscal_periods (many) → profiles (one)
- tax_rates (many) → profiles (one)

## Design Notes

- Denormalized schema optimized for analytics
- Tax rates (`tax_rates`) are user-editable data, not code — rates/brackets change per country and year. The `TaxModel` (code) defines *how* to compute; `tax_rates` defines *what rates* to use.
- Dividend withholding taxes are modeled via transaction_taxes with tax_type=WITHHOLDING, linked to dividend (`income_category='dividends'`) transactions
- portfolio_assets.is_active can be derived from transactions but denormalized for performance
- balance_snapshots anchor the cash balance of an (entity, currency) pair to a known value at a point in time. Transactions with timestamp <= snapshot timestamp are excluded from incremental cash balance computation for that pair.
- manual_values anchor the total value of a manual-tracked portfolio asset at a point in time (`effective_date`), the manual-mode analog of balance_snapshots/prices. All valuation reads consume the ledger and fall back to the legacy `portfolio_assets.current_value_manual` column only when it is empty.

## Schema Migrations

Migrations live in `backend/db/migrations/` as versioned modules (`NNN_name.py`), applied in version order by `db/connection.py:_run_migrations()`. The current schema (`schema.sql`) bakes in the latest shape for fresh installs; migrations bring existing databases up to date incrementally.

### Contract

Each migration module must export two functions:

- `up(conn)` — idempotent apply. Safe to run even when the end-state is already present (uses `IF NOT EXISTS`, existence-guarded `ALTER TABLE`, etc.).
- `verify(conn) -> bool` — **postcondition check**: `True` iff the migration's end-state is present in the schema.

### Runner

The runner is **verification-based**. `schema_migrations` is a cache, not an authority:

```
for each migration module in version order:
    if recorded AND verify(conn):   continue   # end-state already present
    up(conn)                                   # idempotent re-run if stale/missing
    if not verify(conn): raise                 # end-state not reached → fail loudly
    record version (INSERT OR REPLACE)
```

This design makes migration application self-healing:

| DB state | Behavior |
|---|---|
| Fresh install (current `schema.sql`) | verify passes for every migration → each is recorded, `up` runs as a no-op |
| Legacy pre-profiles DB | `008.verify` fails → 008 runs → `profile_id` added + backfilled to `Default` |
| Recorded-but-not-applied (e.g. a bad bootstrap marked 008 applied without running it) | `008.verify` fails → 008 re-runs (idempotent) → repaired on next boot |

### Per-migration postconditions

| Version | `verify` |
|---|---|
| 001_purchase_date | `portfolio_assets` lacks `purchase_date` |
| 002_backfill_snapshots | `True` (pure data backfill, no schema postcondition) |
| 003_stock_splits | `stock_splits` table exists |
| 004_schedule_asset | `schedules` has `portfolio_asset_id` |
| 005_manual_values | `manual_values` table exists |
| 006_transfer_types | `transactions` CHECK includes `TRANSFER_IN` |
| 007_schedule_occurrences | `schedule_occurrences` table exists |
| 008_profiles | `profiles` exists, every ownership table has `profile_id`, and a profile row is present |
| 013_tax_rates | `tax_rates` table exists and `profiles` has `default_fiscal_rule` |

### Design notes

- **Why verify, not the tracking table:** a previous bootstrap recorded all migrations as applied without running them, leaving DBs where `schema_migrations` claimed `008_profiles` was applied while no ownership table had a `profile_id` column. The verification-based runner repairs such DBs on next startup.
- **Default profile seeding** is owned by migration 008 (`_migrate_profiles`); `main.seed_default_profile` is a guarded fallback and no longer creates the schema, so it cannot mask an unmigrated DB.
- **Data-only migrations** (002 backfill, 007 backfill) have no schema postcondition; re-running is idempotent and safe.
- The tracking table is updated with `INSERT OR REPLACE` so re-applied migrations refresh `applied_at`.
- Migrations are also applied when the app is restarted; a recorded-but-broken migration self-heals on the next boot without manual intervention.

## Currency Rate Model: Market vs Applied

The system has two separate mechanisms for currency rates serving different purposes:

### 1. `currencies` table — Market Reference Rate

Time-series of market exchange rates. Used for portfolio valuation, historical analytics, and as a reference baseline.

- Populated periodically from external market data sources
- Represents the mid-market rate at a given timestamp
- Accessed via `GET /currencies/rates/{code}/{base_code}` with optional `at` parameter

### 2. `transactions.fx_rate` — Transaction-Applied Rate

The actual exchange rate applied by the broker/counterparty in a specific operation. Captures the real rate including spreads, commissions, or any deviation from market.

- Recorded at transaction time from the broker's conversion
- Brokers do not publish rates continuously — only observable when a conversion occurs
- Stored per-transaction alongside `payment_currency`

### Why both exist

The two rates can (and often do) differ due to broker spreads. Each serves a distinct purpose:

| Scenario | Market Rate (`currencies`) | Applied Rate (`transactions.fx_rate`) |
|----------|---------------------------|--------------------------------------|
| Portfolio valuation | ✅ Used to price holdings at market value | ❌ Not relevant |
| Cash flow tracking | ❌ Not needed | ✅ Records actual money moved |
| Tax calculation | Reference for FMV computation | Actual proceeds if relevant |
| Performance analytics | Benchmark for return calculation | Used to isolate broker cost impact |
| Spread analysis | Base reference | Compared against to compute broker cost |

**Example:**

```text
Market rate (currencies):  EUR→USD = 1.1000
Broker applied (fx_rate): EUR→USD = 1.0850  (includes 15bps spread)
Transaction invests USD 1,085 using EUR 1,000
```text

### Why no separate "broker rate sheet"

Brokers do not publish continuous rate feeds like market data providers. Their conversion rate is only observable at the moment of a transaction. Modeling it as `transactions.fx_rate` is sufficient and avoids maintaining a separate rate table that would be sparsely populated.
