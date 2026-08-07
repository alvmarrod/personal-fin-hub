# Changelog

All notable changes to the backend service.

## [0.5.0] — 2026-08-07

### Added

- **Structured logging**: All log output is now JSON (via `python-json-logger`). Request ID middleware injects a UUID per request (`X-Request-ID` header) and attaches it to every log line. Log level configurable via `LOG_LEVEL` env var (default `INFO`). Market API client logs request details at `DEBUG` and failures at `WARNING`. APScheduler noise suppressed to `WARNING`.
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
