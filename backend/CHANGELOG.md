# Changelog

All notable changes to the backend service.

## [0.21.0] — 2026-09-03

### Changed

- **Tax per-item columns split**: `GET /analytics/taxable-pnl-extended` items now expose three separate amounts — `native_amount` (gross in the original currency), `display_amount` (plain FX conversion of the native amount at the transaction date, §16.4), and `taxable_amount` (rule-converted §16.2 then exemption-reduced §17.4, in display currency). Each item also carries `tax_policy` (linked exemption name, e.g. `NISA`) and a per-row `fiscal_rule` (frozen for sells, resolved per payment date for dividends).

### Added

- **Per-buy display-currency amount**: each open buy lot in `GET /portfolio-assets` now carries `display_value` — the lot's cost basis converted to the requested `display_currency` at the buy's transaction date (§16.4). When no `display_currency` is given, `display_value` is `null`.

### Fixed

- **Confirmed taxes scoped to the active profile**: `GET /analytics/taxable-pnl-extended` (the Tax page) now filters its confirmed-withholding lookup by the active `transaction_taxes.profile_id` instead of aggregating across every profile. Previously a confirmed tax recorded under another profile could attach to this profile's tax rows and inflate or mis-attribute the Tax Owed figures.

- **Per-entity historical chart failed under a scoped profile**: `GET /analytics/historical?entity_id=...` (the Entities page chart) raised `sqlite3.ProgrammingError: Incorrect number of bindings supplied` when an active profile was set. `get_net_positions_as_of`'s entity branch appends the profile filter twice (inside the `primary_entity` CTE and in the outer `WHERE`) but supplied the profile binding only once. It now passes `_profile_params` once per filter, so the entity-filtered net-position query works under `X-Profile-ID`. The bug was dormant because existing tests never passed `entity_id` on a profile-scoped connection; the Entities page's per-entity chart was the first live caller. 5 new tests cover the query, service, and API paths (+5).

- **Circuit-breaker recovery from market syncs**: `POST /market/sync-prices` and `POST /currencies/sync` gated traffic with `CircuitBreaker.is_open()`, which is true for both `open` and `half-open`. Because only `allow_request()` transitions `open → half-open` after the cooldown and grants the single trial request, the syncs short-circuited forever — the "Market data is temporarily unavailable — using cached data" message persisted even after the Market API recovered. Both syncs now use the new non-consuming `can_proceed()` peek: within the cooldown they still fail fast with the `circuit_open` marker, and once the cooldown elapses they actually probe the service and recover to `closed` on success. The app-health probe (`MarketAPIClient.health_check`) now commits recovery too — `record_success()` on a passing probe, `record_failure()` on a failed one — instead of leaving the circuit stuck in `half-open`.

- **Sell fiscal rule falls back to the profile default**: creating or editing a sell transaction stores the rule from the active fiscal period; when the sell date falls outside every period, the write now uses the profile's `default_fiscal_rule` instead of leaving `fiscal_rule` blank. Tax rows always resolve to an explicit ruleset.

## [0.20.0] — 2026-08-28

### Changed

- **Per-broker FIFO**: realized gains and open-position cost basis are now independent per (portfolio asset, broker). A sell consumes only the buy lots of its own broker, so an asset held at several brokers tracks each position's cost basis separately (§10.1).

### Added

- **Open buy lots in the Portfolio Assets API**: `GET /portfolio-assets` now returns, for each asset with an open position, the buy lots that make up the position (remaining quantity, lot cost basis), grouped per broker. Fully consumed buys and sold-out assets are excluded.

### Fixed

- **Timestamp mixing**: buy sorting no longer errors when stored timestamps mix timezone-aware and naive values (e.g. JPY assets).

## [0.19.0] — 2026-08-27

### Changed

- **Cash flow per-type and per-subcategory detail**: `GET /analytics/cash-flow` now groups by period + type + currency + category (COALESCE of `income_category` and `investment_transaction_category`). Each `CashFlowLine` carries a `category` field. The frontend renders three levels of expandable rows: Inflows/Outflows → component types (INCOME, INVESTMENT_SELL / MONEY_OUT, INVESTMENT_BUY) → individual transactions (lazy-loaded). The stacked bar chart breaks down by type with grouped stacks (Inflows green shades, Outflows red shades). New endpoint `GET /analytics/cash-flow/transactions` returns individual transactions for a specific row on demand.

## [0.18.0] — 2026-08-27

### Added

- **Fees and taxes are cash-impacting (entity main pocket)**: every `transaction_fees` / `transaction_taxes` row is now a real cash-out charged to `entities.main_currency` (new nullable column, migration `018`), converted from its recorded currency at the parent transaction's timestamp with the nearest stored rate when they differ; fee amounts follow the Fees page rules (`FIXED`/`PERCENTAGE`/`BOTH`/`MIN`, percentage base = transaction total). All balance computations include the term — reconciliation walks, injection sizing, snapshot adjustment refresh, and every dashboard/analytics cash figure. Entities without `main_currency` charge fees to the fee's own recorded pair without conversion. Fee-driven deficits on the main pocket produce inferred-cash adjustments under the normal Auto rules, linked to the parent spends. Editing or deleting fees/taxes now triggers reconciliation of every affected pair (`update_full` reconciles after replacing fees). Missing conversion rates surface via the standard banner + rate sync.

- **Dividends display-currency conversion**: `GET /analytics/dividends` now accepts an optional `display_currency`; when provided, each `DividendLine` carries `total_dividends_display` — the per-asset sum converted at each payment's own transaction-date rate (§16.4). Powers the Dividends page's currency selector (card, chart, and table "Amount" column). 4 new tests.

### Changed

- **Unfunded buys inject cash instead of creating snapshots**: when an `INVESTMENT_BUY` exceeds the pair's running balance and no prior snapshot anchors it, the shortfall is now recorded as a standalone injected `BALANCE_ADJUSTMENT` (`balance_snapshot_id = NULL`) at `buy.date − 1 day 23:59:59` (notes "Inferred cash for investment purchases") instead of an auto-created balance snapshot. Same-day unfunded buys merge into one injected row. When a prior snapshot *does* exist, the default is now to debit the known balance — letting it go negative if that reflects reality — rather than silently fabricating a corrective snapshot; the measured balance is taken just before the buy (same-day earlier buys included), fixing under-counted shortfalls for same-timestamp buys. Migration `016` consolidates historical auto-snapshots into this shape. 3 new tests; suite now 1160.
- **Cash-handling choice on all spends**: new optional `cash_handling` field (`inject` | `debit`) on transaction and transfer creation. `None` keeps the smart default; `inject` forces a standalone inferred-cash adjustment even when anchored; `debit` never injects (balance may go negative). Applies to `INVESTMENT_BUY`, `MONEY_OUT`, and the out-leg of `/transfers`. 6 new tests.
- **Cash-handling persistence (reconciliation Phase A)**: the inject/debit choice is now stored — new `transactions.cash_handling` column (`'inject'` | `'debit'`; `NULL` = smart default decided at record time) persisted on create/update and returned by transaction responses. Injected `BALANCE_ADJUSTMENT`s are explicitly attached to the same-day spends they fund via the new `balance_adjustment_links` junction table (one injection may fund several spends; mutually exclusive with `balance_snapshot_id`). Transaction responses expose `cash_handling` plus `attached_transaction_ids` for adjustments. Lifecycle: deleting a spend removes its link — when none remain, its attached injection is deleted too; deleting an adjustment clears its links. Migration `017` adds both structures and backfills links from every existing standalone injection to its next-day spends. 8 new tests.
- **Edit-time injection recalculation (reconciliation Phase B)**: editing a spend now recalculates its attached injection against the spend's new cash impact — raised when the shortfall grows, lowered when it shrinks, removed (with links) when fully funded, created when newly unfunded. Moving a spend to another date/entity/currency detaches it from the old injection (refreshed or removed) and re-attaches/creates at the new slot; changing its type to an inflow detaches entirely. Balance measurements exclude the row being edited, so recomputation is exact rather than incremental. 8 new tests; suite now 1191.
- **Snapshot 409 removed**: creating transactions or schedules dated before the latest balance snapshot no longer fails with `snapshot_conflict`. Every snapshot now self-reconciles at read time, so pre-snapshot records are absorbed by a refreshed corrective adjustment on that snapshot.
- **Null-safe own-adjustment exclusion**: balance recomputation (`get_transactions_between`, `get_balance_at_date`) used `balance_snapshot_id = ?` in its NOT-exclusion clause, which silently dropped standalone adjustments (NULL FK) from the running sum whenever an exclusion was active — replaced with null-safe `IS ?`. Regression-tested. Suite now 1167.
- **Cash balance tracks payment currency**: when a transaction records `payment_currency` different from `currency` (cross-currency trades), the cash balance now reflects the actual pocket where proceeds land — `COALESCE(payment_currency, currency)`. Sells with `payment_currency=JPY` increase the JPY cash pocket (not USD); buys with `payment_currency=JPY` decrease the JPY pocket. The cash-impacting amount is `COALESCE(gross_amount, total_value)` where `gross_amount = total_value × fx_rate`. All 13 cash-balance SQL functions updated. Frontend auto-fills `payment_currency` to the entity's `main_currency` for sells. No schema changes — `payment_currency`, `gross_amount`, `fx_rate` already exist on `transactions`. 8 new tests; suite now 1227.

### Fixed

- **Cross-currency injection targets correct cash pocket**: `_ensure_cash_for_spend`, `_required_injection_for_day`, and `_recalculate_adjustments` now use the spend's cash pocket (`COALESCE(payment_currency, currency)`) and cash-impacting amount (`gross_amount` when available, else `total_value`) instead of `currency` and `total_value`. Cross-currency buys no longer inject into the asset-currency pocket — the inferred-cash adjustment correctly targets the payment-currency pocket where cash actually moves. Doc corrections across 5 files. 1228 tests green.

- **Fee cash-out ignored for entities without main_currency**: `compute_fee_cash_out_at` returned 0 for all queries when `entities.main_currency` was NULL, so fees and taxes were never subtracted from the cash balance of entities without a configured main currency. Now: same-currency fees are subtracted directly; cross-pair fees are still skipped (no conversion available without a main currency). 1 test replaced with 2; suite now 1228.

## [0.17.0] — 2026-08-23

### Added

- **Deep FX rate sync**: `POST /currencies/sync` now backfills full history per currency pair — from the earliest transaction date (minus 7 days) to today, chunked into consecutive ≤1-year windows via the Market API's new `?start=&end=` parameters (max span 1 year/request), falling back to the provider's default window when no transactions exist. Pair results report `windows`/`start`/`end`. 4 new tests.
- **Scheduled rate sync (UC-47)**: new APScheduler job `rate_sync` fires daily at `rate_sync_hour_utc` UTC (default 01:00 — after the global FX close; set `null` to disable) with a 6h misfire grace, keeping closing rates fresh automatically. 2 new tests.

### Changed

- **Total Return is realized-only**: `total_return` in `GET /analytics/performance` = realized trading P&L + dividends over invested historic. Unrealized P&L no longer enters the sum (it stays reported separately as `total_unrealized_pl` and lives in the Portfolio band); interest remains excluded (cash yield, not investment performance).
- **Dividends & interest in the performance summary**: new response fields `total_dividends`, `dividend_yield_pct` (dividends ÷ all-time invested historic × 100) and `total_interest`. Each income payment (`income_category = 'dividends' | 'interest'`) converts to the display currency at its own transaction-date rate, with fallbacks reported via `rate_fallbacks` under the existing `"dividends"` scope and a new `"interest"` scope (added to `PerformanceRateFallback.scope`). 7 new tests.
- **Previous-close FX rate resolution**: historical lookups (`GET /currencies/rates/{code}/{base}?at=` and every analytics conversion) now resolve strictly **on or before** the requested date — never forward (no lookahead bias; a Sunday lookup takes Friday's close instead of Monday's). Non-trading days have no stored FX rows by design and weekends do not count toward staleness: a previous-close resolution is accepted silently unless it is **at least two business days old** (unified rule in `currency_svc.business_days_between` / `is_stale_rate`, §16.4) — only genuinely stale gaps surface as `closest-in-time`. Timestamp comparisons are temporal (`julianday`), fixing mixed `Z`/offset-format handling. 13 new tests.
- **Rate-staleness banners** (cash-flow, income): `RateMetadata` now carries a `stale` flag computed with the same two-business-day rule against the server date; the pages render their "Exchange rates from …" warning only when `stale` is set, so yesterday's fresh close no longer triggers it. 6 frontend tests.
- **Self-contained production image**: the Dockerfile copies the full runtime source (`main.py`, `db/`, `models/`, `routes/`, `scheduler/`, `scripts/`, `services/`) — previously it only baked in two paths and depended on Compose bind-mounting the host tree, which also meant any test run or commit inside `./backend` restarted the live app via `--reload`. The image now runs without hot reload (`uv sync --frozen --no-dev`, unbuffered logs, no bytecode writes), a new `.dockerignore` keeps tests/caches/local data/config out of builds, and Compose mounts only `data/` plus a read-only `config.json`. Services restart with `unless-stopped`.

## [0.16.0] — 2026-08-21

### Added

- **`realized_pl_pct` in `GET /analytics/performance`**: realized P&L as a percentage of the display-currency cost basis of the sold lots (the strict analog of `unrealized_pl_pct`, which divides by the cost basis of held shares). The sold cost basis is converted per sale under its frozen fiscal rule — sell-date rate for `default`/`spain`, per-lot buy-date rates for `japan`, latest rate for `latest` — via a new `ConvertedSale.cost_basis_display` field returned by `convert_sale`. `0.0` when nothing has been sold. 4 new tests.

## [0.15.2] — 2026-08-21

### Fixed

- **Realized gains ignore portfolio-asset deactivation**: `get_buy_sell_transactions` no longer filters `pa.is_active = 1`, so buys/sells of deactivated ("closed") assets reappear in Realized Gains, performance summary realized P&L, and taxable P&L (previously a fully-sold-and-deactivated asset silently vanished from all historical P&L). Current-state views (holdings, valuation, allocation, price-sync targets) keep excluding inactive assets. 2 new tests.

## [0.15.1] — 2026-08-20

### Added

- **Regression tests for projected income**: 2 new tests verifying `get_projected_income` only returns rows for categories with active schedules, and returns empty when no schedules exist.

### Fixed

- **Tax page dividend asset resolution**: `get_dividend_transactions` now joins `entities`, `portfolio_assets`, and `market_assets` to provide entity name, ticker, and market code for dividend items, replacing the raw `#transaction_id` fallback.

## [0.15.0] — 2026-08-20

### Added

- **`cashback` income category**: new `CASHBACK` enum value and migration 014 that recreates the `transactions` and `schedules` tables with updated `income_category` CHECK constraints to accept `salary, other, dividends, interest, cashback`.

### Changed

- **Realized P&L now uses true FIFO lots**: `get_realized_gains` and `_compute_fifo_cost_basis` consume a shared FIFO lot queue (`{quantity, unit_cost, buy_date}`, with `unit_cost = buy.total_value / buy.quantity`) instead of a moving average. This aligns the code with `calculations.md` §10/§11 and makes `total_invested_now` (remaining-lot cost) correct when buys have different unit costs.
- **Performance summary honors `display_currency`**: `GET /analytics/performance` now accepts an optional `display_currency` query parameter (default `USD`) and converts all amounts — portfolio value, invested now/historic, unrealized and realized P&L, and total return — to that currency. `total_invested_historic` is now computed per transaction currency instead of a single summed value, and the response includes a `display_currency` field. 2 new tests.

### Added

- **Taxable P&L — `GET /analytics/taxable-pnl`**: groups taxable realized gains + dividends into fiscal years of a ruleset. A ruleset now carries a **fiscal-year start** (v1 natural year; configurable) and treats **dividends** as taxable income converted at their payment date. Each sell is converted under its frozen `fiscal_rule`; `fiscal_exemptions` reduce the taxable amount of linked transactions (`exemption_rate` % exempt, optional `exemption_amount` fixed allowance converted at the tx date, optional `exemption_rate_limit` cap). Losses pass through unchanged. `rate_fallbacks` now covers `realized_pl | invested_historic | dividends`. New `TaxablePnlSummary`/`TaxablePnlFiscalYear` models + 15 tests.
- **Taxable P&L extended — `GET /analytics/taxable-pnl-extended`**: per-line-item detail (quantity, proceeds, cost basis, P&L, tax owed) with confirmed-vs-computed source badges and per-category tax breakdown. `tax_rates` table + CRUD (`/tax-rates`). `TaxModel` engine with `SavingsCombinedTaxModel` (Spain) and `FlatPerCategoryTaxModel` (Japan). Profile `default_fiscal_rule` column. Seeded Spain progressive and Japan flat rates. 42 new tests.
- **Fiscal periods — `fiscal_periods` + `transactions.fiscal_rule` (migration 012)**: the fiscal rule governing P&L display conversion is now assignable per date range and frozen onto each sell at creation. A new `fiscal_periods` table (`profile_id`, `rule_key`, `start_date`, `end_date` NULL = open-ended) plus a nullable `transactions.fiscal_rule` column. `queries.create_transaction`/`update_transaction` resolve the period containing a sell's date and snapshot it (only for `INVESTMENT_SELL`); editing/deleting a period never changes an already-recorded sell, while editing a sell's timestamp re-resolves its snapshot. `rule_key = 'none'` (no rule) converts identically to `default`.
- **`GET/POST/PUT/DELETE /fiscal-periods`**: profile-scoped CRUD (`services/fiscal_period_svc.py` + `routes/fiscal_periods.py`). Create/update reject overlapping date ranges within a profile (422). `TransactionResponse` now exposes `fiscal_rule`.
- **Per-sale rule conversion in `GET /analytics/performance`**: each sell converts under its frozen `fiscal_rule` snapshot, falling back to the locale-inferred default for legacy/period-less sells. 30 new tests.
- **Fiscal-rule P&L conversion (Phase 1)**: new `services/pnl_rules.py` implements the `PnlRule` registry (`spain`, `japan`, `default` copy of `spain`, `latest` legacy) and routes `GET /analytics/performance` realized P&L through it. `total_invested_historic` is now converted per buy at each purchase date's rate (rule-independent, §16.3). Proceeds recorded via `payment_currency`/`fx_rate` are converted from the payment currency at the sale date (§16.2).
- **`GET /analytics/performance` locale + rule resolution**: accepts `locale` (e.g. `es-ES`) to infer the default rule (`es` → `spain`, `ja` → `japan`, else `default`); the response gains `rule_key` and `rate_fallbacks`.
- **Rate fallback flags (§16.4)**: when the closest stored rate for a date differs from the requested date, or no rate exists at all, the response lists a `PerformanceRateFallback` entry (`reason`: `closest-in-time`/`no-rate`); identical entries aggregate with a `count`. 20 new tests.

### Fixed

- **Python 3.12 datetime adapter deprecation**: `db/queries.py` currency functions (`create_self_rate`, `insert_rate`, `upsert_rate`, `get_rate_at`, `update_rate`) now explicitly call `.isoformat()` on `datetime` parameters before passing to `conn.execute()`, eliminating the `DeprecationWarning: The default datetime adapter is deprecated as of Python 3.12`. Test files updated to match.

## [0.13.0] — 2026-08-14

### Changed

- **`transaction_category` renamed to `investment_transaction_category` (migration 011)**: DB column, API request/response field, and enum (`TransactionCategory` → `InvestmentTransactionCategory`) now reflect that the value (`NORMAL`/`DCA`/`REBALANCE`) is investment-only. Fresh-DB DDL updated; existing DBs migrate via `011_rename_investment_category`. A model validator mirrors the existing `income_category` rule and rejects the field on non-`INVESTMENT_BUY/SELL` types. 11 new tests.

### Added

- **Scheduled buys stamped `DCA`**: transactions materialized from a schedule with type `INVESTMENT_BUY` are stored with `investment_transaction_category = 'DCA'` across all three paths — initial create (`schedule_full_svc`), catch-up, and recurring occurrence (`scheduler.py`). Sells, income, and money-out schedules remain unchanged (no category); rebalance stays manual-only. Scheduler/schedule tests updated (buy → DCA; sell/income → null).

## [0.12.0] — 2026-08-14

### Added

- **Update availability check — `GET /api/v1/updates`**: public endpoint (no profile required) reporting whether a newer `backend/` or `frontend/` release exists in the public GitHub repository. It lists GitHub Releases, filters by `tag_name` prefix (`backend/` vs `frontend/`), takes the greatest semantic version per side, and compares against the backend's own `pyproject.toml` version and the frontend's self-reported `?frontend_version=`. Results are cached server-side for `update_check.cache_seconds` (default 3600); fail-open on GitHub errors (never a false `outdated`); short-circuits to `{"enabled": false}` when `update_check.enabled` is off. New `services/update_svc.py` (stdlib semver helper, no new deps) and `services/config.py` `update_check_*` properties. 16 new tests.

## [0.11.0] — 2026-08-13

### Added

- **Income analytics grouped by category**: `GET /analytics/income-by-source` now groups realized income by `period + entity_id + income_category + currency`, and `GET /analytics/projected-income` groups schedule occurrences by `period + entity_id + income_category`. `IncomeBySourceLine` gains `type` and `income_category` fields so consumers can classify income into categories (Salary / Other / Dividends / Interest) instead of only by receiving entity. 6 new tests.
- **Unified income model — `INCOME` type + `income_category` (migration 010)**: the `MONEY_IN`, `DIVIDEND`, and `INTEREST` transaction types are consolidated into a single `INCOME` type, classified by the new `income_category` column (CHECK salary, other, dividends, interest) on `transactions` and `schedules`. The `transactions.type` CHECK is updated accordingly. `TransactionCreate`/`TransactionUpdate` accept `income_category` and enforce that it is only set on `INCOME` and that dividend metadata fields require `income_category='dividends'`; schedule create/full/update persist it and the scheduler copies it onto every materialized transaction. Legacy rows without a category fall back to an entity derivation (`EMPLOYER` → salary, else other) in the analytics layer. 5 new tests.

## [0.10.3] — 2026-08-12

### Added

- **Paced, freshness-aware price sync (UC-46)**: `POST /market/sync-prices` now accepts `full`, `pace` (seconds between symbol requests) and `max_age_hours` (freshness skip window) query params. Incremental syncs skip symbols whose `market_assets.last_synced_at` is newer than `max_age_hours`; `full=true` ignores freshness. Requests are paced with a fixed sleep to avoid the provider's burst-throttling (HTTP 500). A single-flight lock ensures only one sync runs at a time (concurrent callers get `busy: true`). A scheduler cron job (config `market_api.sync_cron_hours`, default `[0, 12]` UTC) runs a full paced refresh (`sync_cron_pace_seconds`, default 5) with `max_instances=1` + coalesce. New `market_assets.last_synced_at` column (migration 009), updated only on success. New `services/market_sync_svc.py`. 3 new tests.

## [0.10.2] — 2026-08-12

### Added

- **Invested amount and value in the price-history chart**: `GET /prices/chart/{market_code}` now computes and returns `invested` (cumulative FIFO cost basis) and `value` (net quantity × price) per date alongside the existing `price` field — null before the first transaction for that asset. The Portfolio Assets page renders the three series in the same widget: price on the left Y axis, invested and investment value on the right Y axis. 1 new test.

### Fixed

- **Manual-tracked assets no longer hit the market API**: the bulk price-sync endpoint (`POST /market/sync-prices`) now excludes `tracking_mode = 'manual'` assets from its market-code query. Previously manual assets (e.g. mutual-fund codes like `JP90C0007G10`) were sent to the external market API on every sync, producing 500s and retries for symbols the provider doesn't trade. The `get_price` per-symbol endpoint is unaffected (caller explicitly requests the symbol). 1 new test.

## [0.10.1] — 2026-08-12

### Added

- **Manual valuation ledger writes (UC-45)**: `POST /portfolio-assets` and `PUT /portfolio-assets/{id}` now transparently upsert the payload's `current_value_manual` into the `manual_values` snapshot ledger whenever the asset is `tracking_mode = manual` and a value is present. `effective_date` (new optional field on `PortfolioAssetCreate`) defaults to today, enabling backdated corrections. `POST /portfolio-assets/{id}/manual-values` now UPSERTs on `(portfolio_asset_id, effective_date)` instead of failing on the unique constraint, so revaluing a date replaces that date's row. New `queries.upsert_manual_value`. 14 new tests; suite now 960.

### Fixed

- **Holdings value chart missed the newest valuation (UC-45)**: `GET /prices/value-chart` sampled dates at weekly (or monthly) intervals and stopped at the last sample at or before the range end. A manual valuation effective after the final sample date — e.g. one entered today — was never plotted, so the chart's last point showed the previous value (up to ~6 days stale). The endpoint now always appends the exact `end_date` as the final sample, so the latest manual valuation (and the final days of market prices) are reflected. 2 new tests; suite now 960.
- **Duplicate auto-snapshots corrupted cross-currency buy balances**: `_ensure_cash_for_buy` blindly inserted a new `balance_snapshots` row for every `INVESTMENT_BUY` without checking for an existing snapshot at the same `(entity_id, currency, timestamp)`. Multiple same-date buys (common when entering backdated trades at `T00:00:00`) spawned duplicate rows at identical timestamps, but `get_previous_snapshot()` returns only one row (`ORDER BY timestamp DESC LIMIT 1`). Subsequent `_ensure_cash_for_buy` calls then computed shortfalls against only the visible snapshot, producing an inflated snapshot amount. After all buys were processed the orphan snapshot left positive cash — e.g. entity EUR liquidity equal to the oldest same-date buy cost instead of 0. The function now upserts amounts when a snapshot already exists at `snapshot_ts`. 2 new tests; suite now 962.

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

- **Transfer leg types**: `TRANSFER_IN`/`TRANSFER_OUT` added to `TransactionType` and the `transactions.type` CHECK constraint. Transfer legs are cash-flow neutral — excluded from income/expense analytics (Cash Flow, Income by Source) while still netting directionally into entity cash balances. `TRANSFER` remains as a reserved legacy value and is never written. Existing databases are migrated by rebuilding the `transactions` table (CHECK constraints cannot be altered in place); legacy `INCOME`/`MONEY_OUT` transfer pairs are left untouched and must be re-created manually.

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
