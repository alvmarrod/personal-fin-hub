# Calculations Inventory

This document inventories every UI component across all views and maps it to its corresponding calculation as defined in `calculations.md`.

## Legend

| Status | Meaning |
|--------|---------|
| ✅ | Correct and aligned with `calculations.md` |
| ❌ | Mismatch — implementation does not match the documented calculation |
| ⚠️ | Not defined in `calculations.md` — needs review or future definition |

---

## Dashboard (`/`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| MetricCard | Portfolio Value | Section 5: Total Portfolio Value at Date X | ✅ | `total_portfolio_value = total_asset_value + total_cash`. Includes both investments and cash balance. |
| MetricCard | Cash Balance | Section 2.2: Total Cash at Date X | ✅ | `get_cash_balance()` — snapshot-aware, sums all entity/currency pairs. |
| MetricCard | Total Invested | Section 6: Total Return (`total_invested`) | ✅ | Sum of `total_value` for all `INVESTMENT_BUY` transactions (cost basis). |
| MetricCard | Total Return | Section 6: Total Return | ✅ | `total_return = total_investments_value + total_cash - total_invested`, displayed as percentage. |
| LineChart | Historical Portfolio Value | Section 5: Total Portfolio Value at Date X | ✅ | `get_historical_values()` — includes both asset values and cash balance at each date point. |
| DoughnutChart | By Entity | Section 7.1: By Entity | ✅ | `_get_allocation_by_entity()` — merges investment holdings + cash per entity. |
| PieChart | By Asset Class | Section 7.2: By Asset Class | ✅ | `get_asset_allocation('asset_class')` — groups assets by class + adds CASH as its own class. |
| CrossTabTable | Asset Class × Entity Summary | Section 4: Holdings by Entity at Date X | ✅ | `get_holdings_by_entity()` — merges investments + cash under `CASH` asset class per entity. |

---

## Entities (`/entities`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table column (per asset class) | Dynamic (e.g. "VI", "FI") | Section 3.3: Asset Value | ✅ | `getEntityValue(entityId, assetClass)` — filters `holdingsByEntity` by entity + asset class, sums `current_value`. |
| Table column | Liquidity | Section 2.1: Cash Balance at Date X (per entity) | ✅ | `getEntityLiquidity(entityId)` — filters `holdingsByEntity` where `asset_class === 'CASH'`, sums `current_value`. |
| Table column | Assets | Section 3.3: Asset Value | ✅ | `getEntityAssets(entityId)` — filters `holdingsByEntity` where `asset_class !== 'CASH'`, sums `current_value`. |
| LineChart | Historical Value — {Entity Name} | Section 4: Holdings by Entity at Date X | ✅ | `get_historical_values(entityId)` — now includes both asset values (quantity × price) and cash balance for the entity at each date point. |
| Warning icon | (no label, tooltip) | Not defined | ⚠️ | Shows when entity has dependents (transactions, balance snapshots, or schedules). Disables delete button. Purely a UI guard, not a financial calculation. |

---

## Currencies (`/currencies`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| MetricCard (per currency) | Total Holdings by Currency (incl. Cash) | Section 15.3: Total Exposure per Currency | ✅ | Combines `holdingsData.latest_raw[code]` (investment value in currency) + `cashBalances` grouped by currency. |
| StackedAreaChart | Holdings Over Time | Section 15.3 over time | ✅ | Combines `holdingsData.series` (investment values over time per currency) + `cash-by-currency-history` (cash balance over time per currency). |
| LineChart | Exchange Rate History | Not defined | ⚠️ | Displays historical exchange rates from `/currencies/rate-chart`. Purely informational — shows rate trends, not used in any portfolio calculation. |
| Select | Display Currency | Not defined | ⚠️ | UI control that sets the `display_currency` query parameter for the holdings endpoint. Affects how holdings are grouped, not a calculation itself. |
| Select | Base Currency | Not defined | ⚠️ | UI control that sets the `base_currency` for the rate chart. Purely informational. |
| Button | Sync Rates | Not defined | ️ | Triggers `POST /currencies/sync` to fetch latest exchange rates. An action, not a calculation. |

---

## Income (`/income`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| MetricCard | Realized This Month | Not defined | ️ | Sums `total_value` from `cashFlow` API for transactions of type `MONEY_IN`, `INTEREST`, `DIVIDEND` within the current month (1st of month to today). A cash flow aggregation, not a balance calculation. |
| MetricCard | Projected This Month | Not defined | ⚠️ | Client-side projection: generates recurring schedule occurrences for the current month using `generateOccurrences()`, sums their `total_value`. Based on schedule periodicity, not actual transactions. |
| MetricCard | Next Month | Not defined | ️ | Same projection logic as "Projected This Month" but for the next calendar month. |
| MetricCard | Projected (Range) | Not defined | ⚠️ | Total sum of all projected schedule occurrences across the entire chart date range. |
| MetricCard | Active Sources | Not defined | ️ | Count of income schedules (`MONEY_IN`, `INTEREST`, `DIVIDEND`) with a non-null `entity_id`. A simple count, not a financial calculation. |
| StackedBarChart | Income by Source | Not defined | ⚠️ | Two datasets per source: realized (from `incomeBySource` API, grouped by month) and projected (from schedule occurrences). Realized uses pastel blues, projected uses pastel greens. |
| Table | Income Sources | Not defined | ⚠️ | Per source: realized (this month), projected (this month), total (all periods), schedule description/periodicity, next payment date. Combines realized cash flow + schedule projections. |
| Table | Recent Income Transactions | Not defined | ⚠️ | Raw transaction data filtered to `MONEY_IN`, `INTEREST`, `DIVIDEND` types (excluding `DIVIDEND`), sorted by timestamp descending, paginated at 10 per page. |
| Table | Dividends | Not defined | ️ | Raw transaction data filtered to `DIVIDEND` type only, sorted by timestamp descending, paginated at 10 per page. |

---

## Transactions (`/transactions`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table | (main transactions table) | Not defined | ⚠️ | Displays raw transaction data with client-side filtering by time range, type, entity, and currency. Columns: Date, Type, Entity, Amount, Currency, Category, Notes. Paginated at 20 per page. No aggregation — pure data listing. |
| Filter bar | Time presets (3m, 6m, 1y, All, Custom) | Not defined | ⚠️ | Client-side date range filter. Notably `6m` = -3 months to +3 months (future-inclusive). Not a calculation, a UI control. |
| Filter bar | Type filters (All, Income, Expenses, Investment) | Not defined | ⚠️ | Client-side type filter mapping: `income` = `[MONEY_IN, INTEREST, DIVIDEND]`, `expense` = `[MONEY_OUT]`, `investment` = `[INVESTMENT_BUY, INVESTMENT_SELL]`. UI control. |
| Filter bar | Entity dropdown | Not defined | ⚠️ | Client-side entity filter. UI control. |
| Filter bar | Currency dropdown | Not defined | ️ | Client-side currency filter. UI control. |
| Badge | Type | Not defined | ️ | Color-coded label: `success` (MONEY_IN, INTEREST), `danger` (MONEY_OUT), `primary` (INVESTMENT_BUY), `info` (INVESTMENT_SELL), `warning` (DIVIDEND). Purely visual. |
| Badge | Currency | Not defined | ⚠️ | Always `badge-info` style. Purely visual. |
| Badge | Category | Not defined | ⚠️ | `badge-warning` if `transaction_category` present, else `-`. Purely visual. |

---

## Balance Snapshots (`/balance-snapshots`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table | (snapshots table) | Section 8: Balance Snapshots (data display) | ✅ | Displays raw snapshot data: Date, Entity, Currency, Amount, Notes. Sorted by timestamp descending, paginated at 20 per page. Direct CRUD data, no derived calculation. |
| Filter | Entity dropdown | Not defined | ⚠️ | Client-side entity filter. UI control. |

---

## Summary of Issues

### ❌ Mismatches (require fix)

None — all identified mismatches have been resolved.

### ✅ Fixed

| # | View | Component | Issue | Fix Applied |
|---|------|-----------|-------|-------------|
| 1 | Dashboard | MetricCard "Portfolio Value" | Was showing only asset value, excluding cash. Contradicted Section 5 definition. | Modified `get_dashboard()` to return `total_value + cash` as `total_portfolio_value`. |
| 2 | Entities | LineChart "Historical Value — {Entity}" | Was showing only asset values (quantity × price), excluding cash for the entity. Contradicted Section 4 definition. | Added `get_entity_cash_as_of()` function and modified `get_historical_values()` to include entity cash when `entity_id` is provided. |

### ⚠️ Not Defined in `calculations.md` (require future definition or acceptance as UI-only)

| Category | Components | Notes |
|----------|-----------|-------|
| Income projections | Projected This Month, Next Month, Projected (Range), Active Sources, Income by Source chart, Income Sources table | Schedule-based forward projections. Could be defined as a new section "Schedule Projections" in `calculations.md`. |
| Cash flow aggregation | Realized This Month | Period-based cash flow sum. Could be defined under a new section "Period Cash Flow". |
| Raw data listings | Recent Income Transactions, Dividends table, Transactions table, Balance Snapshots table | No aggregation — pure CRUD data display. No calculation definition needed. |
| UI controls | All filters, selects, buttons, badges | Not calculations. No definition needed. |
| Exchange rates | Exchange Rate History chart | Informational display of rate trends. Not used in portfolio calculations. Could be noted in Section 9. |
