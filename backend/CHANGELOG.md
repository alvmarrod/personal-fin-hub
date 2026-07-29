# Changelog

All notable changes to the backend service.

## [0.2.0] — In development

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

## [0.1.0] — Initial release

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
