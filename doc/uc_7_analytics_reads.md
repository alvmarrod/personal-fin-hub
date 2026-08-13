# Tier 7 — Analytics Reads

Read-only views that aggregate data from transactions, portfolio assets, prices, and currencies. All analytics follow the **uniform currency conversion rule**: when `display_currency` is provided, all values are converted using market rates from the `currencies` table before aggregation. If no rate exists for a currency, the value is included as-is (no conversion).

---

## UC-24: View Dashboard Summary

**Trigger**: User opens the Dashboard (`/`)

**Modeling decision**:

- Displays 4 metric cards + 3 charts + 1 cross-tab table
- All values converted to `display_currency` (user-selectable, defaults to USD)

**Components**:

- **Portfolio Value**: `total_asset_value + total_cash`, converted to display_currency
- **Cash Balance**: sum of all per-entity, per-currency cash balances (snapshot-aware), converted
- **Total Invested**: sum of `total_cost` for all holdings, converted
- **Total Return**: `(total_portfolio_value - total_invested) / total_invested × 100`
- **Historical Value Chart**: portfolio value over time (asset value + cash at each date), converted
- **By Entity Doughnut**: entity allocation (holdings + cash per entity), converted
- **By Asset Class Pie**: asset class allocation (+ CASH as its own class), converted
- **Asset Class × Entity Cross-Tab**: entity breakdown by asset class, converted

**Currency model**:

- `display_currency` parameter passed to all backend endpoints
- Backend converts each value using `get_rate(currency, display_currency)` from `currencies` table
- If rate is missing, value is included unconverted
- Quick actions (+Add Asset, +Add Income) use `POST /transactions/full` with user-provided currency

**Entities affected**: `transactions` (read), `portfolio_assets` (read), `market_assets` / `prices` (read), `currencies` (read), `balance_snapshots` (read), `entities` (read)

**UI pages**: Dashboard (`/`)

---

## UC-25: View Holdings with P&L

**Trigger**: User views current holdings with profit/loss

**Modeling decision**:

- Per active portfolio asset: net_quantity, avg_cost, current_value, unrealized_pnl, weight_pct
- `current_value` = `net_quantity × latest_price` (auto mode) or latest entry from `manual_values` table (manual mode)
- `unrealized_pnl` = `current_value - total_cost`
- `weight_pct` = `current_value / total_portfolio_value × 100`
- Manual-mode `price_source` is `manual`; `price_as_of` = the valuation's `effective_date` (see UC-45)

**Currency model**:

- Values are in the asset's native currency (from `market_assets.currency_code`)
- When `display_currency` is provided, all values converted for display
- `avg_cost` is always in the asset's native currency (not converted)

**Entities affected**: `portfolio_assets` (read), `transactions` (read), `prices` (read), `market_assets` (read), `manual_values` (read)

**UI pages**: Dashboard (`/`), Entities page (`/entities`)

---

## UC-26: View Asset Allocation

**Trigger**: User views portfolio composition by different dimensions

**Modeling decision**:

- Multi-dimension grouping: layer, asset_type, currency, asset_class, entity
- Each dimension groups holdings differently but uses the same underlying data

**Dimensions**:

- `layer`: core, reserve, satellite (from `portfolio_assets.layer`)
- `asset_type`: STOCK, ETF, ETC, etc. (from `market_assets.asset_type`)
- `currency`: asset's native currency (from `market_assets.currency_code`)
- `asset_class`: FI, VI, REIT, Gold, etc. (from `market_assets.asset_class`) + CASH as its own class
- `entity`: primary entity (first transaction's entity for each portfolio asset)

**Currency model**:

- When `display_currency` is provided, all values converted before grouping
- `asset_class` dimension includes CASH as a separate class (from `get_cash_balance_by_currency()`)
- Cash is converted using market rates, same as investment values

**Entities affected**: `portfolio_assets` (read), `market_assets` (read), `transactions` (read), `prices` (read), `balance_snapshots` (read), `currencies` (read)

**UI pages**: Dashboard (`/`)

---

## UC-27: View Cash Flow

**Trigger**: User views cash inflows and outflows over time

**Modeling decision**:

- Groups `transactions` by period (month/year) + type + currency
- `total_in` = INCOME + INVESTMENT_SELL
- `total_out` = MONEY_OUT + INVESTMENT_BUY
- `net` = total_in - total_out
- BALANCE_ADJUSTMENT, TRANSFER, TRANSFER_IN, and TRANSFER_OUT excluded from sums (transfer legs are cash-flow neutral; they are not income or expense)

**Currency model**:

- When `display_currency` is provided, all values converted to display_currency
- Line items retain their original currency for detail views
- Rate metadata returned alongside data (which rates were used, latest timestamp)

**Entities affected**: `transactions` (read), `currencies` (read)

**UI pages**: Cash Flow page (`/cash-flow`)

---

## UC-28: View Income by Source

**Trigger**: User views income breakdown by category, entity, and period

**Modeling decision**:

- Filters `type` = INCOME
- Groups by period + entity_id + type + currency + income_category
- Joins `entities` for entity name
- `income_category` is resolved in SQL: explicit `transactions.income_category` when set, otherwise derived — income into an `EMPLOYER` entity → `salary`, else `other`
- Returns: period, entity_id, entity_name, type, income_category, currency, total_value, count
- Frontend prefers the backend-provided `income_category` and falls back to the same derivation for legacy rows

**Currency model**:

- When `display_currency` is provided, all `total_value` amounts converted
- Income Sources table displays values in native currency (no conversion)
- Charts and metric cards use converted values

**Entities affected**: `transactions` (read), `entities` (read), `currencies` (read)

**UI pages**: Income page (`/income`)

---

## UC-29: View Projected Income

**Trigger**: User views projected future income from schedules

**Modeling decision**:

- Backend computes projected occurrences from schedules with type = INCOME
- Generates occurrences based on periodicity within date range
- Groups by period, entity, type, and income_category
- `income_category` comes from the schedule's explicit `income_category` when set, otherwise derived from the schedule's entity (`EMPLOYER` → `salary`, else `other`)

**Currency model**:

- Projected amounts are in `schedule.currency`
- When `display_currency` is provided, converted using latest exchange rates
- Same conversion logic as realized income (UC-28)

**Entities affected**: `schedules` (read), `entities` (read), `currencies` (read)

**UI pages**: Income page (`/income`)

---

## UC-30: View Dividends

**Trigger**: User views dividend income grouped by portfolio asset

**Modeling decision**:

- Filters `income_category = 'dividends'`
- Groups by `portfolio_asset_id` + `currency`
- Joins for asset metadata (name, market_code, ticker)

**Currency model**:

- Dividends display in their native currency (the `currency` field on the transaction)
- `dividend_currency` and `dividend_payment_currency` provide additional detail about the FX path
- No display_currency conversion in the dividends detail view

**Entities affected**: `transactions` (read), `portfolio_assets` / `market_assets` (read)

**UI pages**: Income page (`/income`), Dividends page (`/dividends`)

---

## UC-31: View Fees & Taxes

**Trigger**: User views aggregated fees and taxes

**Modeling decision**:

- Joins `transaction_fees` + `transactions` for fees
- Joins `transaction_taxes` + `transactions` for taxes
- Fee computation: `_compute_fee_amount()` — FIXED uses `fixed_amount`, PERCENTAGE uses `percentage × tx.total_value / 100`, BOTH sums them, MIN takes the minimum

**Currency model**:

- Fees and taxes display in their own currency (from `transaction_fees.currency` / `transaction_taxes.currency`)
- No display_currency conversion — amounts are shown as-is in the fee/tax's native currency

**Entities affected**: `transaction_fees` (read), `transaction_taxes` (read), `transactions` (read)

**UI pages**: Fees & Taxes page (`/fees-taxes`)

---

## UC-32: View Realized Gains (FIFO)

**Trigger**: User views realized profit/loss from investment sales

**Modeling decision**:

- Processes all INVESTMENT_BUY/SELL in chronological order per portfolio asset
- FIFO lot queue: each buy creates a lot with `{quantity, unit_cost}`. On sell, oldest lots consumed first
- `cost_basis = Σ(consumed lots' cost)`
- `realized_pl = sell_proceeds - cost_basis`
- Remaining partial lots carry forward

**Currency model**:

- All calculations in the asset's native currency (from `market_assets.currency_code`)
- No display_currency conversion — realized gains are in the asset's original denomination
- Cross-currency impact (fx_rate on sell) is captured in the transaction but not used in FIFO computation. FIFO uses `total_value` which is in `currency`

**Entities affected**: `transactions` (read), `portfolio_assets` / `market_assets` (read)

**UI pages**: Performance page (`/performance`)

---

## UC-33: View Historical Portfolio Value

**Trigger**: User views portfolio value over time (line chart)

**Modeling decision**:

- For each bucket date in range:
  1. Get net positions as of that date (BUY/SELL quantities)
  2. Look up price of each portfolio asset as of that date (binary search on sorted price history)
  3. Sum `net_qty × price` for all positions
  4. Add manual-tracked assets using their `manual_values` snapshot as of that date (UC-45) instead of market price
  5. Add cash balance at that date (snapshot-aware)
  6. Convert to `display_currency` if provided
  7. Return `(date, total_value)`

**Currency model**:

- Asset values are in native currencies, converted to display_currency using market rates as of each date
- Cash is snapshot-aware and converted per-date
- If no rate exists for a currency on a date, value is included unconverted
- Entity filtering: optionally compute for a single entity (used by Entities page)

**Entities affected**: `transactions` (read), `prices` (read), `balance_snapshots` (read), `market_assets` (read), `currencies` (read), `manual_values` (read)

**UI pages**: Dashboard (`/`), Entities page (`/entities`)

---

## UC-34: View Performance Summary

**Trigger**: User views combined performance (unrealized + realized)

**Modeling decision**:

- Combines:
  - Holdings P&L (unrealized): from UC-25
  - Realized gains: from UC-32
- `total_pnl = Σ(unrealized_gain) + Σ(realized_gain)`

**Currency model**:

- Both unrealized and realized are in asset native currencies
- When `display_currency` is provided, both are converted before summing
- Exchange rate used is the latest available rate

**Entities affected**: `transactions` (read), `portfolio_assets` / `market_assets` (read), `prices` (read), `currencies` (read)

**UI pages**: Performance page (`/performance`)

---

## UC-35: View Transaction List

**Trigger**: User views the transactions page or any filtered list of transactions

**Modeling decision**:

- Read-only list of all transactions with client-side filtering
- Columns: Date, Type, Entity, Amount (total_value), Currency, Category, Notes
- Sorted by timestamp descending (most recent first)
- Paginated (20 per page)

**Filtering**:

- Time range: presets (3m, 6m, 1y, All, Custom). Notably `6m` = -3 months to +3 months (future-inclusive for scheduled items)
- Type: All, Income (`INCOME`), Expenses (`MONEY_OUT`), Investment (`INVESTMENT_BUY`, `INVESTMENT_SELL`)
- Entity: dropdown filtered to non-deleted entities
- Currency: dropdown filtered to currencies present in transactions

**Currency model**:

- Amounts display in the transaction's native `currency` (no conversion)
- The filter bar shows the raw `total_value` in the transaction's currency
- Entity name is joined from `entities` table

**Rejected alternatives**:

- Server-side filtering → rejected: transaction volume is manageable client-side. All data is fetched once and filtered in the browser
- Currency conversion in the list → rejected: the transaction list is a data ledger, not an analytics view. Values should be shown as recorded

**Entities affected**: `transactions` (read), `entities` (read)

**UI pages**: Transactions page (`/transactions`)

---

## UC-36: List Income Transactions

**Trigger**: User views recent income transactions on the Income page

**Modeling decision**:

- Filtered subset of transactions: `type` = INCOME with `income_category != 'dividends'` (excluding dividends — dividends have their own table via UC-37)
- Sorted by timestamp descending (most recent first)
- Paginated (10 per page)
- Columns: Date, Type, Entity, Amount, Currency, Notes

**Currency model**:

- Amounts display in the transaction's native `currency` (no conversion)
- This is a raw data listing, not an aggregated view

**Rejected alternatives**:

- Including dividends (`income_category='dividends'`) in this list → rejected: dividends have specific metadata (dividend_type, record_date, payment_date) and are displayed in a separate table (UC-37)
- Merging with the general transaction list (UC-35) → rejected: the Income page shows a curated view of income-specific transactions, separate from the full ledger

**Entities affected**: `transactions` (read), `entities` (read)

**UI pages**: Income page (`/income`)

---

## UC-37: List Dividends

**Trigger**: User views recent dividend transactions on the Income page

**Modeling decision**:

- Filtered subset of transactions: `income_category = 'dividends'`
- Sorted by timestamp descending (most recent first)
- Paginated (10 per page)
- Columns: Date, Asset, Gross Amount, Dividend Currency, Withholding Tax, Net Amount, Payment Date

**Currency model**:

- Displays in the dividend's native currencies: `dividend_currency` for gross, `dividend_payment_currency` for net
- Withholding tax amount is in `dividend_currency`
- No display_currency conversion — this is a detailed ledger view

**Rejected alternatives**:

- Including in the general income list → rejected: dividends have unique metadata that other income categories don't have. A dedicated table provides better UX
- Showing only `currency` field → rejected: the two-currency model (dividend_currency vs dividend_payment_currency) is important for understanding the FX impact on dividends

**Entities affected**: `transactions` (read), `portfolio_assets` / `market_assets` (read), `transaction_taxes` (read)

**UI pages**: Income page (`/income`)

---

## UC-43: Auto-Detect and Adjust Stock Splits in Portfolio Charts

**Trigger**: User views the Holdings Value Over Time chart (`/portfolio-assets`), or any analytics endpoint that computes historical holding values via `GET /prices/value-chart?display_currency=...&start_date=...&end_date=...`.

**Modeling decision**:

- Stock splits cause market price APIs to return split-adjusted prices for all historical dates, but transaction quantities and unit prices remain unadjusted.
- Without adjustment, charts show incorrect values for holding periods before the split (net_quantity × split_adjusted_price is lower than real value).
- The system auto-detects splits by comparing each buy transaction's `unit_price` with the market price on the same date (`buy_unit_price / market_price`). If the ratio is ≥2 and within 15% of an integer, a split is inferred.
- Once detected, the split ratio is applied to all value computations for dates within the affected buy-to-sell holding period (average-cost tracked). When the split-affected shares are fully sold, the adjustment stops.
- Post-split re-buys are not affected (market prices match transaction prices on their dates → no split detected).
- **Currency conversion**: when `display_currency` is provided, each asset's value (`qty × price`) is converted from the asset's native currency (`market_assets.currency_code`) to the display currency using the latest exchange rate from the `currencies` table. Assets already in the display currency are left unchanged.

**Components**:

1. **`detect_stock_splits(conn)`** (db/analytics_queries.py): Scans all buy transactions. For each, fetches the market price on the buy date. If `unit_price / market_price ≥ 2` and rounds cleanly to an integer (within 15% tolerance), records the split ratio per (portfolio_asset_id, buy_date).
2. **Split period calculation** (routes/prices.py, `portfolio_value_chart`): For each market_code with detected splits, processes all buy/sell transactions chronologically (FIFO) to determine the start and end date of each split-affected holding period. Stores `(start_date, end_date, ratio)` tuples.
3. **Value adjustment** (routes/prices.py, `portfolio_value_chart`): In the date loop, after computing `value = qty × price`, if the current date falls within a split period for that market_code, the value is multiplied by the split ratio.
4. **Currency conversion** (routes/prices.py, `portfolio_value_chart`): After split adjustment, if `display_currency` is set and differs from the asset's native currency, the value is multiplied by the latest exchange rate via `currency_svc.get_rate()`.

**Example**: User buys 100 shares at ¥900/unit (pre-split). Market API returns ¥200 for the same date (post-split adjusted). Ratio = 900/200 = 4.5 ≈ integer 5 (15% tolerance met). Chart values for this holding period are multiplied by 5: 100 × 200 × 5 = ¥100,000 (correct pre-split equivalent), instead of 100 × 200 = ¥20,000 (wrong).

**Entities affected**: `transactions` (read), `prices` (read), `market_assets` (read, for currency)

**UI pages**: Portfolio Assets page (`/portfolio-assets`) — Holdings Value Over Time chart

---

## UC-44: Manual Stock Split Registration

**Trigger**: `GET /prices/value-chart` detects a buy whose `unit_price` is ≥2× the nearest market price and rounds to integer (within 15% tolerance), but no same-day market price exists → returned in `flagged_splits` alongside chart data. Frontend shows notification banner above the chart.

**Modeling decision**:

- Splits stored in `stock_splits` table with **one-split-per-asset-per-calendar-year** constraint (`UNIQUE(market_code, year)`). Prevents duplicates and limits confirmations to once per natural year.
- Three-tier detection per chart load:
  1. **Confirmed**: Splits already in `stock_splits` → applied automatically.
  2. **Auto-detected**: Same-day price match (≥2×, ≤15% tolerance) → auto-registered if no split exists for that asset+year.
  3. **Flagged**: No same-day match but ratio qualifies → returned in `flagged_splits`. User confirms via `POST /stock-splits`. Rejected with 409 if year already has a split.
- Auto-detections are persisted so user can audit/delete mistakes (`DELETE /stock-splits/{id}`). Deleting causes next load to re-detect or re-flag.
- `split_date` gates which buys get the ratio — only buys before the split date are adjusted. Post-split re-buys unaffected.

**Components**:

1. **`stock_splits` table**: `id`, `market_code`, `split_date`, `ratio`, `created_at`. Yearly unique index.
2. **`POST /stock-splits`**: Creates split. 409 if year exists.
3. **`DELETE /stock-splits/{id}`**: Removes split.
4. **`GET /stock-splits`**: Lists all splits, optional `market_code` filter.
5. **`portfolio_value_chart`**: Merges confirmed + auto-detected splits. Flags ambiguous. Returns `PortfolioValueChartResponse` (`data` + `flagged_splits`).
6. **UI**: Notification banner above Holdings chart. Confirm modal shows buy date, buy price, market price, inferred ratio. POST on confirm.

**Entities affected**: `stock_splits` (new), `transactions` (read), `prices` (read)

**UI pages**: Portfolio Assets page — notification banner + confirm modal
