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

All dashboard components support currency conversion via `display_currency` parameter (Section 9). Values are converted to the selected display currency before aggregation.

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Select | Display Currency | Section 9: Currency Conversion | ✅ | Currency selector in header, defaults to USD. Passes `display_currency` to all API calls. |
| MetricCard | Portfolio Value | Section 5: Total Portfolio Value at Date X | ✅ | `total_portfolio_value = total_asset_value + total_cash`. All values converted to display currency. |
| MetricCard | Cash Balance | Section 2.2: Total Cash at Date X | ✅ | `get_cash_balance_by_currency()` — snapshot-aware, sums all entity/currency pairs after conversion. |
| MetricCard | Total Invested | Section 6: Total Return (`total_invested`) | ✅ | Sum of `total_cost` for all holdings, converted to display currency. |
| MetricCard | Total Return | Section 6: Total Return | ✅ | `total_return = total_investments_value + total_cash - total_invested`, displayed as percentage. |
| LineChart | Historical Portfolio Value | Section 5: Total Portfolio Value at Date X | ✅ | `get_historical_values(display_currency=...)` — includes both asset values and cash balance at each date point, all converted. |
| DoughnutChart | By Entity | Section 7.1: By Entity | ✅ | `_get_allocation_by_entity(display_currency=...)` — merges investment holdings + cash per entity, converted. |
| PieChart | By Asset Class | Section 7.2: By Asset Class | ✅ | `get_asset_allocation('asset_class', display_currency=...)` — groups assets by class + adds CASH, converted. |
| CrossTabTable | Asset Class × Entity Summary | Section 4: Holdings by Entity at Date X | ✅ | `get_holdings_by_entity(display_currency=...)` — merges investments + cash under `CASH` asset class per entity, converted. |

---

## Entities (`/entities`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table column (per asset class) | Dynamic (e.g. "VI", "FI") | Section 3.3: Asset Value | ✅ | `getEntityValue(entityId, assetClass)` — filters `holdingsByEntity` by entity + asset class, sums `current_value`. |
| Table column | Liquidity | Section 2.1: Cash Balance at Date X (per entity) | ✅ | `getEntityLiquidity(entityId)` — filters `holdingsByEntity` where `asset_class === 'CASH'`, sums `current_value`. |
| Table column | Assets | Section 3.3: Asset Value | ✅ | `getEntityAssets(entityId)` — filters `holdingsByEntity` where `asset_class !== 'CASH'`, sums `current_value`. |
| LineChart | Historical Value — {Entity Name} | Section 4: Holdings by Entity at Date X | ✅ | `get_historical_values(entityId, displayCurrency)` — includes both asset values (quantity × price) and cash balance for the entity at each date point, all converted to display currency. |
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

All income page aggregation components support currency conversion via `display_currency` parameter (Section 9). The Income Sources table displays values in their native currency, while metric cards and charts convert to the selected display currency.

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Select | Display Currency | Section 9: Currency Conversion | ✅ | Currency selector in header, defaults to USD. Passes `display_currency` to API calls. |
| Warning | Rate Info Callout | Section 9: Currency Conversion | ✅ | Shows when conversion is applied. Displays latest rate timestamp and rates used. |
| MetricCard | Realized This Month | Not defined | ✅ | Sums `total_value` from `cashFlow` API for transactions of type `INCOME` within the current month. Converted to display currency. |
| MetricCard | Projected This Month | Not defined | ✅ | Backend projection via `projectedIncome` API: generates recurring schedule occurrences for the current month. Converted to display currency. |
| MetricCard | Next Month | Not defined | ✅ | Same projection logic as "Projected This Month" but for the next calendar month. Converted to display currency. |
| MetricCard | Projected (Range) | Not defined | ✅ | Total sum of all projected schedule occurrences across the entire chart date range. Converted to display currency. |
| MetricCard | Active Sources | Not defined | ✅ | Count of unique entity-currency combinations from projected income. A simple count, not a financial calculation. |
| StackedBarChart | Income by Type | Not defined | ✅ | Grouped by income category (Salary, Other, Dividends, Interest). Category resolved server-side: explicit `income_category` on the transaction/schedule wins; legacy rows fall back to income into an `EMPLOYER` entity → Salary, else Other. Two datasets per category: realized (from `incomeBySource` API, grouped by month) and projected (from `projectedIncome` API). All values converted to display currency. |
| Table | Income Sources | Not defined | ✅ | Per source-currency: categories (Salary/Other/Dividends/Interest), realized (this month), projected (this month), total (all periods), schedule description/periodicity, next payment date. **Displays in native currency** (no conversion). |
| Table | Recent Income Transactions | Not defined | ⚠️ | Raw transaction data filtered to `INCOME` type excluding `income_category='dividends'`, sorted by timestamp descending, paginated at 10 per page. |
| Table | Dividends | Not defined | ⚠️ | Raw transaction data filtered to `income_category='dividends'`, sorted by timestamp descending, paginated at 10 per page. |

---

## Transactions (`/transactions`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table | (main transactions table) | Not defined | ⚠️ | Displays raw transaction data with client-side filtering by time range, type, entity, and currency. Columns: Date, Type, Entity, Amount, Currency, Category, Notes. Paginated at 20 per page. No aggregation — pure data listing. |
| Filter bar | Time presets (3m, 6m, 1y, All, Custom) | Not defined | ⚠️ | Client-side date range filter. Notably `6m` = -3 months to +3 months (future-inclusive). Not a calculation, a UI control. |
| Filter bar | Type filters (All, Income, Expenses, Investment) | Not defined | ⚠️ | Client-side type filter mapping: `income` = `[INCOME]`, `expense` = `[MONEY_OUT]`, `investment` = `[INVESTMENT_BUY, INVESTMENT_SELL]`. UI control. |
| Filter bar | Entity dropdown | Not defined | ⚠️ | Client-side entity filter. UI control. |
| Filter bar | Currency dropdown | Not defined | ️ | Client-side currency filter. UI control. |
| Badge | Type | Not defined | ️ | Color-coded label: `success` (INCOME), `danger` (MONEY_OUT), `primary` (INVESTMENT_BUY), `info` (INVESTMENT_SELL). Purely visual. |
| Badge | Currency | Not defined | ⚠️ | Always `badge-info` style. Purely visual. |
| Badge | Category | Not defined | ⚠️ | `badge-warning` showing `income_category` for `INCOME` rows, `investment_transaction_category` (NORMAL/DCA/REBALANCE) for investment rows, else `-`. Purely visual. |

---

## Balance Snapshots (`/balance-snapshots`)

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Table | (snapshots table) | Section 8: Balance Snapshots (data display) | ✅ | Displays raw snapshot data: Date, Entity, Currency, Amount, Notes. Sorted by timestamp descending, paginated at 20 per page. Direct CRUD data, no derived calculation. |
| Filter | Entity dropdown | Not defined | ⚠️ | Client-side entity filter. UI control. |

---

## Performance (`/performance`)

All performance page aggregation components support currency conversion via `display_currency` (Section 9 / Section 16). The Realized Gains table displays values in their native currency, while metric cards convert to the selected display currency.

| Component | Title / Label | Calculation (`calculations.md`) | Status | Current Implementation |
|-----------|--------------|--------------------------------|--------|----------------------|
| Select | Display Currency | Section 16 | ✅ | Currency selector in page header, defaults to EUR in the UI store. Passes `display_currency` (and `locale`) to the analytics API. |
| MetricCard | Portfolio Value | Section 5: Total Portfolio Value at Date X | ✅ | `total_portfolio_value`, converted to display currency (Section 9). |
| MetricCard | Total Invested Now | Section 10.2: Cost Basis of a Position | ✅ | `total_invested_now` = sum of remaining FIFO lots' cost, converted to display currency (Section 9). |
| MetricCard | Unrealized P&L % | Section 12 + Section 10.2 | ✅ | `unrealized_pl_pct` relative to `total_invested_now`. Delta styling (▲/▼ + color) via `valueVariant`. |
| MetricCard | Unrealized P&L | Section 12 | ✅ | `total_unrealized_pl` = current value − cost basis, converted to display currency at latest rate (Section 9). |
| MetricCard | Total Invested Historic | Section 16.3 | ✅ | `total_invested_historic` converted per buy at each purchase date's rate (rule-independent). Rate fallback flags reported via `rate_fallbacks`. |
| MetricCard | Total Return | Section 6 + Section 16 | ✅ | `total_return_pct` = (unrealized + realized) / invested historic, with the Section 16.3 denominator. |
| MetricCard | Realized P&L | Section 16.2 | ✅ | `total_realized_pl` converted per sell via its frozen `fiscal_rule` snapshot (period-based; locale-inferred default when NULL). |
| Table | Realized Gains | Section 11 (native, rule-independent) | ✅ | Per-row native FIFO P&L in the asset's currency — no display conversion. |

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
| Raw data listings | Recent Income Transactions, Dividends table, Transactions table, Balance Snapshots table | No aggregation — pure CRUD data display. No calculation definition needed. |
| UI controls | All filters, selects, buttons, badges | Not calculations. No definition needed. |
| Exchange rates | Exchange Rate History chart | Informational display of rate trends. Not used in portfolio calculations. Could be noted in Section 9. |
