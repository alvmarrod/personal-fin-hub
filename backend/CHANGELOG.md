# Changelog

All notable changes to the backend service.

## [0.11.0] — 2026-08-12

### Added

- **Manual valuation ledger writes (UC-45)**: `POST /portfolio-assets` and `PUT /portfolio-assets/{id}` now transparently upsert the payload's `current_value_manual` into the `manual_values` snapshot ledger whenever the asset is `tracking_mode = manual` and a value is present. `effective_date` (new optional field on `PortfolioAssetCreate`) defaults to today, enabling backdated corrections. `POST /portfolio-assets/{id}/manual-values` now UPSERTs on `(portfolio_asset_id, effective_date)` instead of failing on the unique constraint, so revaluing a date replaces that date's row. New `queries.upsert_manual_value`. 14 new tests; suite now 958.

## [0.10.0] — 2026-08-11

### Added

- **Auto-resolve FX rate on cross-currency transactions**: `transaction_svc.create()` and `update()` now auto-populate `fx_rate` from the `currencies` table when `payment_currency` differs from `currency` and no rate is provided. `gross_amount` and `net_amount` are computed from `total_value × fx_rate`. User-provided values are preserved; clearing on edit re-resolves. 5 new tests. Total suite now 944.

## [0.9.1] — 2026-08-11

### Fixed

- **Docker healthcheck timeout**: `MarketAPIClient.health_check()` now bypasses the retry machinery and performs a single HTTP `GET /health` with a 2s timeout. Previously it went through `_request()` which retried 3 times at 3s each, taking 9s+ when the external Market API was unreachable. Docker Compose's healthcheck (`timeout: 3s`) killed the `curl` call before the backend responded, marking the container unhealthy and preventing the frontend from starting on a fresh clone.
- **`price_source` for assets with prices but no transactions**: `get_holdings()` previously reported `price_source = "none"` for portfolio assets that had synced market prices but zero quantity (no buy transactions). The frontend displayed a misleading "No price data" warning. Now reports `price_source = "market-api"` with `current_value = null` — the price is available, just no holding to value yet.
- **Portfolio chart unified currency**: `/prices/value-chart` now accepts an optional `display_currency` query parameter. When provided, each asset's value is converted from its native currency to the display currency via `currency_svc.get_rate()`. Manual-tracked assets are converted too. Previously all values were in native currency, making the stacked area chart meaningless with mixed-currency holdings.

## [0.9.0] — 2026-08-11

### Added

- **Transport-level retry**: `MarketAPIClient._request()` retries transient failures with exponential backoff +20% jitter (default 3 attempts, 0.5s base, 10s max, configurable). Retried: `ConnectError`, `TimeoutException`, HTTP `5xx`, and `429` (honors `Retry-After`). Other `4xx` (incl. `404` → `MarketAPINotFound`) are never retried.
- **Circuit breaker**: new `services/api_resilience.py` with a thread-safe per-`base_url` breaker (`closed → open → half-open → closed`), shared across request threads and the scheduler. Open = fail fast with `MarketAPIUnavailable` (no timeout stall); half-open = a single trial request after the cooldown. Defaults: 5 consecutive failures → open, 60s cooldown (configurable via `market_api.circuit_failure_threshold` / `circuit_cooldown_seconds`).
- **Fail-fast sync loops**: `POST /market/sync-prices` and `POST /currencies/sync` short-circuit when the breaker is open — returning `circuit_open: true` + per-item `skipped` entries instead of `N × timeout`. Partial-failure per-pair/per-symbol error shape preserved.
- **Health circuit fields**: `/api/v1/health` reports `checks.market_api_circuit` (`closed`/`open`/`half-open`) and `checks.market_api_last_success_at` (ISO timestamp or `null`) without forcing additional attempts against an open circuit.
- **Stale-data signal**: `HoldingLine` and `PortfolioAssetResponse` gain `price_source` (`market-api` | `transaction-fallback` | `manual` | `none`) and `price_as_of`; holdings and `GET /portfolio-assets` responses carry per-line metadata so the frontend can warn users when prices are missing or fall back to transaction purchase prices. Valuation math unchanged.
- **Config keys**: `market_api.retry_attempts`, `retry_base_delay`, `retry_max_delay`, `circuit_failure_threshold`, `circuit_cooldown_seconds` in `config.json`.
- **Tests**: 51 new tests — 38 in `tests/test_api_resilience.py` (breaker state machine + `_request` integration + loop fail-fast), 3 health circuit tests, 6 holdings-metadata tests, 2 portfolio-assets propagation tests, 2 projected-income datetime tests. Total suite now 936.

### Fixed

- **`/analytics/projected-income` datetime crash**: `get_projected_income()` compared offset-aware `datetime.now(UTC)` against offset-naive datetimes parsed from schedule dates stored without timezone, raising `TypeError: can't compare offset-naive and offset-aware datetimes`. Fixed by forcing UTC on all parsed dates in `parse_date()`.

## [0.8.0] — 2026-08-11

### Added

- **Automated database backups**: new `services/backup_svc.py` backs up `data/finhub.db` using the stdlib `sqlite3.Connection.backup()` API — consistent under concurrent writes, unlike a plain file copy. Backups are verified after creation (`PRAGMA integrity_check` + row-count sanity), stored in `BACKUP_DIR` (default `<db dir>/backups`) as `finhub.db-YYYYMMDD-HHMMSS.bak` with mode 0600, and pruned to `BACKUP_RETENTION` (default 7) newest.
- **Daily schedule**: APScheduler job `backup_daily` fires at `BACKUP_CRON` (default `03:00`, `HH:MM`) in `BACKUP_TIMEZONE` (IANA; container-local by default — set it explicitly), with `misfire_grace_time=3600`.
- **Startup catch-up**: on boot, if the daily cutover has passed and no backup exists for the current day, a `daily-catchup` backup is created before migrations run.
- **Migration backups**: `init_db()` now returns `(fresh, applied)`; when migrations apply to an existing DB, exactly two backups surround them — pre-migration (reusing the daily catch-up file when it already ran this boot) and post-migration. Skipped on fresh installs.
- **Backup status in `/health`**: `checks.backup` reports `ok` / `stale` / `never` / `disabled` (informational only, no paths exposed).
- **Backup/restore CLI**: `make backup` and `make restore` (direct: `uv run python -m scripts.backup` / `scripts.restore`). Restore refuses while the backend is running (health-check guard, `--force` to override) and preserves the current DB as `finhub.db.pre-restore-<timestamp>`.
- **Tests**: 22 tests in `tests/test_backup_svc.py` covering create/verify/prune, daily-due logic across timezones, startup and migration backup flows, env parsing, and restore; scheduler test asserts the `backup_daily` job registration. Total suite now 879 tests.

## [0.7.2] — 2026-08-10

### Fixed

- **Verification-based migration runner**: `_run_migrations` now checks each migration's postcondition (`verify(conn)`) instead of trusting the `schema_migrations` tracking table. A migration recorded as applied but whose schema changes are missing — e.g. the 0.7.1 bootstrap recorded `008_profiles` without ever adding `profile_id` columns — is re-applied idempotently on the next boot, repairing affected databases automatically.
- **`verify()` postconditions on all migrations**: every module in `db/migrations/` now exports a `verify()` function; the blind "mark everything applied" bootstrap branch was removed.
- **`seed_default_profile` no longer masks unmigrated DBs**: default profile seeding is owned by migration 008; `main.seed_default_profile` is now a guarded fallback that only seeds an existing, empty `profiles` table.

## [0.7.1] — 2026-08-10

### Fixed

- **Legacy DB migration bootstrap**: The migration runner incorrectly skipped all migrations on pre-migration-system databases, leaving `profile_id` columns missing. Now inspects ownership tables for `profile_id` before assuming a fresh schema.
- **Profile migration per-table commits**: `_migrate_profiles` now commits after each table instead of once at the end, shrinking the window of partial migration state.
- **Migration 006 compatibility**: `transactions_new` DDL now includes `profile_id` column + index, so migration 006 can safely re-run after migration 008.
- **Scheduler profile scoping**: Replaced silent `try/except` in `_scoped_profile` with explicit `isinstance(conn, ProfileScopedConnection)` check.
- **Connection leak in seed_currencies**: Missing `conn.close()` added on early-return and success paths.

## [0.7.0] — 2026-08-07

### Added

- **DB migration versioning**: `db/migrations/` directory with 7 numbered migration modules. New `schema_migrations` table tracks which migrations have been applied. Runner in `_run_migrations()` applies only unapplied migrations in version order. Bootstrap logic marks existing migrations as applied on fresh DBs. Replaces ad-hoc inline SQL + Python in `connection.py`. 3 new tests — total suite now 727 tests.

## [0.6.0] — 2026-08-07

### Added

- **UTC timezone policy**: `_to_iso()` normalizes all timestamps to `YYYY-MM-DDTHH:MM:SS` on storage (no `Z`, no microseconds). Scheduler, analytics, and balance queries use `datetime.now(UTC)`. Uniform format across all DB rows guarantees correct SQL string comparisons. One new format test — total suite now 724 tests.
- **Timezone preference**: Frontend timezone selector in Settings. Browser detection on first visit via `Intl.DateTimeFormat`. Timestamps rendered in the user's selected timezone.

## [0.5.0] — 2026-08-07

### Added

- **Structured logging**: All log output is now JSON (via `python-json-logger`). Request ID middleware injects a UUID per request (`X-Request-ID` header) and attaches it to every log line. Log level configurable via `LOG_LEVEL` env var (default `INFO`). Market API client logs at `DEBUG`, failures at `WARNING`. APScheduler noise suppressed to `WARNING`.
- **Health check depth**: `/health` now returns per-component status (`database`, `market_api`) instead of a static 200. DB failure returns 503; API failure returns 200 with `degraded` status.
- **Health check tests**: 4 unit tests covering all status paths — total suite now 723 tests.
- **Dev tooling**: `make test` / `make lint` with backend and frontend subtargets. `make changelog-check` + CI job validates `CHANGELOG.md` headers match current version. `scripts/commit-msg-check.py` + pre-commit `commit-msg` hook enforces conventional commit format.
- **Release automation**: On push to `main` with a new version, CI creates a `vX.Y.Z` tag and a GitHub Release with combined changelog notes.
- **CI badges**: Backend coverage badge via shields.io. Auto-updated on `main` pushes.

## [0.4.0] — 2026-08-04

### Added

- **`schedule_occurrences` table**: Decouples scheduler deduplication from editable transaction fields. Records `(schedule_id, occurrence_date, transaction_id)` when a schedule materializes. The scheduler checks this table before creating any transaction — if a row exists, the fire is skipped regardless of manual edits to the materialized transaction's date, amount, or notes. The `[schedule:N]` tag in `transactions.notes` is retained as a label but no longer used for deduplication. Migration backfills existing tagged transactions.

- **PerformanceSummary — revised fields**: Renamed `total_invested` → `total_invested_now` (FIFO cost basis of current holdings). Added `total_invested_historic` (all-time sum of `INVESTMENT_BUY` transactions) and `unrealized_pl_pct` (unrealized P&L as a percentage of current cost basis). `total_return_pct` now uses the historic denominator, preventing distortion when shares are sold (the numerator included realized gains from sold shares while the old denominator excluded their cost).

- **Transfer leg types**: `TRANSFER_IN`/`TRANSFER_OUT` added to `TransactionType` and the `transactions.type` CHECK constraint. Transfer legs are cash-flow neutral — excluded from income/expense analytics (Cash Flow, Income by Source) while still netting directionally into entity cash balances. `TRANSFER` remains as a reserved legacy value and is never written. Existing databases are migrated by rebuilding the `transactions` table (CHECK constraints cannot be altered in place); legacy `MONEY_IN`/`MONEY_OUT` transfer pairs are left untouched and must be re-created manually.

### Changed

- **Docker Compose**: Frontend now depends on backend with `condition: service_healthy` healthcheck instead of simple startup order.
- **Scheduler catch-up**: Newly created schedules with past `start_date` now immediately execute missed fires via `catch_up_single_schedule()`. Global catch-up on restart no longer skips when `last_shutdown` is today — each schedule is evaluated individually against its own start date.
- **Schedule investment support**: `ScheduleCreate`/`schedules` table now support `portfolio_asset_id`. Scheduler passes it through to materialized transactions and calls `_resolve_investment_fields` to auto-compute quantity/unit_price from market price. Frontend schedule modal shows asset selector for INVESTMENT_BUY/SELL types.
- **Manual asset valuations**: New `manual_values` table with `(portfolio_asset_id, value, effective_date)` — time-series ledger for manual-tracked assets, analogous to `prices` for auto assets. `GET/POST/DELETE /portfolio-assets/{id}/manual-values` endpoints. `get_holdings()`, `get_historical_values()`, and `portfolio_value_chart` now read from `manual_values` instead of the single `current_value_manual` column. Manual assets now appear in dashboard charts and historical portfolio views with full audit trail.
- **Investment transaction defaults**: `_resolve_investment_fields` now defaults `quantity=1, unit_price=total_value` when only `total_value` is provided, ensuring FIFO cost basis and P&L computation work even without market price data.

### Fixed

- **Edit transaction lost fees/taxes**: Editing an investment transaction no longer silently drops fees and taxes. Added `DELETE FROM transaction_fees/taxes WHERE transaction_id` queries and a `PUT /{tx_id}/full` compound endpoint that atomically replaces old fee/tax rows in the same transaction. The `update()` helper in `transaction_svc` now accepts an optional `conn` parameter for use inside compound operations.

## [0.3.0] — 2026-07-29

### Added

- **Stock split registration** (UC-44): `stock_splits` table with yearly unique constraint. `POST/GET/DELETE /stock-splits` endpoints. Three-tier detection: confirmed DB records, auto-detect (same-day price match), flagged for user confirmation. `PortfolioValueChartResponse` wraps chart `data` + `flagged_splits`.
- **Holdings chart — carry-forward estimates**: When no price exists before a date, the earliest available price is used as fallback. Data points flagged as `estimated`.
- **Holdings chart — All range**: `MIN(timestamp)` from both `transactions` and `prices` determines the chart start instead of hardcoded `2020-01-01`.
- **`get_net_positions_as_of`**: `include_inactive` param so historically held (now-deactivated) assets appear in the chart.

### Changed

- **`portfolio_value_chart`**: Monthly intervals for spans >2 years, weekly otherwise. Split detection now reads from `stock_splits` table alongside auto-detection. Returns `PortfolioValueChartResponse` (breaking: response now wrapped with `data` + `flagged_splits`).
- **`get_holdings()`**: Optional `conn` parameter to reuse caller's DB connection instead of opening a second one.

## [0.2.0] — 2026-06-14

### Added

- **Dashboard P&L fields**: `unrealized_pl` and `realized_pl` added to `DashboardSummary`. Unrealized computed from holdings (market value minus cost basis), realized from average-cost sell transactions, both converted to display currency.
- **Portfolio Assets enrichment**: `PortfolioAssetResponse` now includes `current_value` and `unrealized_pl_pct` fields. `list_all()` joins holdings data per asset and optionally converts values to a unified `display_currency`.
- **Average-cost basis for holdings**: `_compute_fifo_cost_basis()` processes all buy/sell transactions chronologically per asset, correctly computing average cost of remaining shares after sells. Replaces naive `SUM(all buys)` that inflated cost basis on buy-sell-rebuy cycles.
- **Portfolio Assets holdings chart**: `GET /prices/value-chart` now includes historically held assets even after deactivation by passing `include_inactive=True` to `get_net_positions_as_of()`.
- **Stock split auto-detection**: `detect_stock_splits()` compares buy unit_prices with market prices on the buy date. Splits are inferred when the ratio is ≥2 and rounds to a clean integer (15% tolerance). The `portfolio_value_chart` endpoint tracks split-affected holding periods via average-cost tracking and multiplies chart values by the detected ratio, correcting pre-split holding values that would otherwise appear deflated by split-adjusted market prices.
- **CHANGELOG.md**: Both frontend and backend now have changelogs.

### Changed

- **Dashboard**: `get_dashboard()` now calls `get_realized_gains()` and includes realized P&L. Rate cache extended to include realized gain currencies.
- **Portfolio Assets**: `GET /portfolio-assets` accepts optional `display_currency` query param for unified value display.
- **MyPy**: Tightened type annotations in `portfolio_asset_svc.py`.

## [0.1.0] — 2026-06-01

### Core

- FastAPI application with Uvicorn server
- SQLite database with denormalized schema (20+ tables, raw sqlite3, no ORM)
- Automatic schema migration and seed data on startup

### Transactions

- Money in / money out (income, expense)
- Investment buy / sell with auto cash-injection via balance snapshots
- Dividend and interest income recording
- Transfers between entities with fixed and percentage fees
- Configurable taxes per transaction
- Investment auto-calculation: fill any 2 of {amount, quantity, unit price}, backend resolves the third

### Scheduler

- APScheduler background job for recurring transactions
- Catch-up execution for missed schedules
- Configurable periodicity: one-off, daily, weekly, monthly, quarterly, annually, custom intervals

### Analytics

- Portfolio valuation with currency conversion
- Historical portfolio value over time with investment value breakdown
- Asset allocation by entity and by asset class
- Cash flow analysis by period
- Income tracking: realized, projected, by source
- Performance: unrealized and realized P&L with average-cost basis
- Holdings by entity with native and unified currency breakdown
- Cumulative invested calculation per currency

### Entities, Assets & Currencies

- Multi-entity support (broker, bank, employer, exchange)
- Market assets (stock, ETF, ETC, fund, index fund, crypto) with type and class
- Portfolio assets with layer (core/reserve/satellite), DCA, TER, desired allocation
- Multi-currency with FX rate sync from external API
- Configurable base currency

### Market Data

- External Market API integration for price and FX data
- Price history storage per market code
- FX rate history storage per currency pair
- One-click sync endpoint for portfolio asset prices

### Balance Snapshots

- Point-in-time balance recording per entity and currency
- Auto-generated snapshots on investment buys when cash is insufficient

### Fiscal Exemptions

- Tax-exempt account tracking (NISA, ISA, 401k, etc.)
- Configurable rates and limits

### Development

- Pre-commit hooks: ruff (lint + format), mypy (strict), markdownlint
- 708 unit and integration tests (pytest)
- Type-safe with full mypy coverage (zero production errors)
