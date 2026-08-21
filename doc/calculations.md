# System Calculations Reference

This document describes how financial values are computed throughout the system. It serves as the authoritative reference for implementing or modifying any calculation logic.

---

## Index

- [System Calculations Reference](#system-calculations-reference)
  - [Index](#index)
  - [1. Transaction Types and Cash Impact](#1-transaction-types-and-cash-impact)
  - [2. Cash Balance at Date X](#2-cash-balance-at-date-x)
    - [2.1 Per Entity and Currency](#21-per-entity-and-currency)
    - [2.2 Total Cash at Date X](#22-total-cash-at-date-x)
    - [2.3 Total Cash at Date X in Currency Y](#23-total-cash-at-date-x-in-currency-y)
  - [3. Asset Valuation at Date X](#3-asset-valuation-at-date-x)
    - [3.1 Net Quantity](#31-net-quantity)
    - [3.2 Price Lookup](#32-price-lookup)
    - [3.3 Asset Value](#33-asset-value)
    - [3.4 Manual Tracking Mode](#34-manual-tracking-mode)
  - [4. Holdings by Entity at Date X](#4-holdings-by-entity-at-date-x)
  - [5. Total Portfolio Value at Date X](#5-total-portfolio-value-at-date-x)
  - [6. Total Return](#6-total-return)
  - [7. Allocation Calculations](#7-allocation-calculations)
    - [7.1 By Entity](#71-by-entity)
    - [7.2 By Asset Class](#72-by-asset-class)
  - [8. Balance Snapshots and Adjustment Mechanism](#8-balance-snapshots-and-adjustment-mechanism)
    - [Concept](#concept)
    - [First Snapshot](#first-snapshot)
    - [Subsequent Snapshots](#subsequent-snapshots)
    - [Automatic Recalculation](#automatic-recalculation)
    - [Deleting a Snapshot](#deleting-a-snapshot)
    - [Balance at Date X with Snapshots](#balance-at-date-x-with-snapshots)
    - [Constraints](#constraints)
  - [9. Currency Conversion](#9-currency-conversion)
  - [10. Cost Basis](#10-cost-basis)
    - [10.1 FIFO Lot Queue at Date X](#101-fifo-lot-queue-at-date-x)
    - [10.2 Cost Basis of a Position at Date X](#102-cost-basis-of-a-position-at-date-x)
  - [11. Realized Gains/Losses](#11-realized-gainslosses)
    - [11.1 Per Sale Transaction](#111-per-sale-transaction)
    - [11.2 Cumulative Realized Gain/Loss at Date X](#112-cumulative-realized-gainloss-at-date-x)
    - [11.3 Realized P&L Percentage](#113-realized-pl-percentage)
  - [12. Unrealized Gains/Losses](#12-unrealized-gainslosses)
    - [12.1 Unrealized P&L Percentage](#121-unrealized-pl-percentage)
  - [13. Per-Asset P&L](#13-per-portfolio-asset-pl)
  - [14. Dividend Yield](#14-dividend-yield)
    - [14.1 Trailing Yield (yield on current value)](#141-trailing-yield-yield-on-current-value)
    - [14.2 Yield on Cost](#142-yield-on-cost)
  - [15. Currency Exposure Summary](#15-currency-exposure-summary)
    - [15.1 Cash Exposure per Currency](#151-cash-exposure-per-currency)
    - [15.2 Asset Exposure per Currency](#152-asset-exposure-per-currency)
    - [15.3 Total Exposure per Currency](#153-total-exposure-per-currency)
    - [15.4 Exposure as a Percentage](#154-exposure-as-a-percentage)
  - [16. P&L Display-Currency Conversion (Fiscal Rules)](#16-pl-display-currency-conversion-fiscal-rules)
    - [16.1 Native P&L (rule-independent)](#161-native-pl-rule-independent)
    - [16.2 Rule Set](#162-rule-set)
    - [16.3 Invested Historic (buy-side conversion)](#163-invested-historic-buy-side-conversion)
    - [16.4 Rate Lookup and Fallback](#164-rate-lookup-and-fallback)
  - [17. Taxable P&L and Tax Computation (Tax Page)](#17-taxable-pl-and-tax-computation-tax-page)
    - [17.1 Ruleset extension](#171-ruleset-extension)
    - [17.2 Realized gains](#172-realized-gains)
    - [17.3 Dividends](#173-dividends)
    - [17.4 Exemption](#174-exemption)
    - [17.5 Fiscal-year grouping](#175-fiscal-year-grouping)
    - [17.6 Tax categories](#176-tax-categories)
    - [17.7 Tax model](#177-tax-model)
    - [17.8 Tax rates (data)](#178-tax-rates-data)
    - [17.9 Computed tax](#179-computed-tax)
    - [17.10 Confirmed tax](#1710-confirmed-tax)
    - [17.11 Tax resolution](#1711-tax-resolution)
    - [17.12 Per-item detail](#1712-per-item-detail)
    - [17.13 Profile default ruleset](#1713-profile-default-ruleset)
  - [Appendix: Calculations Not Currently Defined](#appendix-calculations-not-currently-defined)

---

## 1. Transaction Types and Cash Impact

Every transaction has a type that determines its effect on cash balance.

| Type | Cash Impact | Description |
| ---- | ----------- | ----------- |
| INCOME | Positive | External cash received as income (salary, other, dividends, interest, cashback — see `income_category`) |
| MONEY_OUT | Negative | External cash withdrawal from an entity |
| INVESTMENT_BUY | Negative | Cash spent to acquire assets |
| INVESTMENT_SELL | Positive | Cash received from selling assets |
| TRANSFER_IN | Neutral | Incoming leg of an entity-to-entity transfer; excluded from income/expense sums, adds to the receiving entity's cash balance |
| TRANSFER_OUT | Neutral | Outgoing leg of an entity-to-entity transfer; excluded from income/expense sums, subtracts from the sending entity's cash balance |
| BALANCE_ADJUSTMENT | Excluded | System-generated reconciliation entry; explicitly filtered out of all cash flow calculations |

Every `INCOME` transaction carries an `income_category` ∈ {salary, other, dividends, interest, cashback}. The category is a strict subclassification of income: dividends are identified by `income_category = 'dividends'` and carry the dividend metadata fields (dividend_type, record_date, payment_date, dividend_currency, dividend_payment_currency, dividend_fx_rate); interest by `income_category = 'interest'`; cashback by `income_category = 'cashback'` (debit card cashback and similar rewards). There is no separate dividend/interest/cashback transaction type.

The canonical cash impact for any transaction on `total_value` is:

- Add `total_value` if type is `INCOME`, `INVESTMENT_SELL`, or `TRANSFER_IN`.
- Subtract `total_value` if type is `MONEY_OUT`, `INVESTMENT_BUY`, or `TRANSFER_OUT`.
- No effect otherwise (e.g., `TRANSFER` reserved value, `BALANCE_ADJUSTMENT`).

Income/expense analytics (Cash Flow, Income by Source) sum only `INCOME`/`INVESTMENT_SELL` as inflows and `MONEY_OUT`/`INVESTMENT_BUY` as outflows — `TRANSFER_IN`/`TRANSFER_OUT` are never counted as income or expense.

---

## 2. Cash Balance at Date X

### 2.1 Per Entity and Currency

The cash balance for a specific `entity` and `currency` at a given `date X` is computed using one of two paths.

**Path A — A balance snapshot exists prior to date X, or no snapshot at all:**

1. Find the most recent `balance_snapshot` for this `entity` and `currency` with a timestamp strictly before `date X`.
2. Start from the `snapshot.amount`, or from zero applying all transactions from the beginning if no snapshot exists.
3. Walk forward through all transactions for this `entity` and `currency`, from the snapshot timestamp up to `date X - 1`.
   1. Note: `BALANCE_ADJUSTMENT` transactions on `date X - 1` are the only non-zero cash-impact transactions expected on that date, as they are auto-generated. Any other cash-impact transaction on `date X - 1` would mean Path B applies instead.
4. Apply each transaction's cash impact (Section 1) to the running balance.

The result is: `snapshot.amount` plus the net cash flow of all intervening transactions.

**Path B — A balance snapshot exists exactly at date X:**

1. Find the `balance_snapshot` for this `entity` and `currency` with a timestamp exactly on `date X`.
2. Start from the `snapshot.amount` and apply all transactions for this `entity` and `currency` on `date X`.

### 2.2 Total Cash at Date X

The system-wide cash balance at `date X` is the sum of all per-entity-per-currency balances (Section 2.1) across all `entity`–`currency` pairs.

### 2.3 Total Cash at Date X in Currency Y

1. Compute `Total Cash at Date X` (Section 2.2), which is broken down at `entity`–`currency` level.
2. For each `entity`–`currency` pair where `currency` differs from `currency Y`, apply the exchange rate for `date X - 1`.
   1. Note: `date X - 1` is used because exchange rates are end-of-day closing values.
3. Sum all converted amounts to produce the total in `currency Y`.

---

## 3. Asset Valuation at Date X

### 3.1 Net Quantity

For each portfolio asset, the `net_quantity` held at `date X` is:

1. Sum all `INVESTMENT_BUY` quantities with `timestamp <= date X`.
2. Subtract all `INVESTMENT_SELL` quantities with `timestamp <= date X`.

Only portfolio assets with `net_quantity > 0` are included in valuation.

### 3.2 Price Lookup

The `price_as_of_X` for a portfolio asset at `date X` is determined by the following priority:

1. **Prices table**: The most recent entry in the prices table (looked up by the portfolio asset's `market_code`) with `timestamp <= date X`. If multiple prices exist, the one with the latest timestamp at or before `date X` is selected.
2. **Transaction fallback**: If no price exists in the prices table, fall back to the `unit_price` of the most recent `INVESTMENT_BUY` transaction for that `portfolio_asset_id` with `timestamp <= date X`. This ensures that an asset's value is always reflected from the moment it is purchased, even before market prices are manually entered.
3. **Zero value**: If neither a prices table entry nor a transaction fallback exists, the portfolio asset contributes zero value.

### 3.3 Asset Value

```text
asset_value = net_quantity × price_as_of_X
```text

- `net_quantity`: as defined in Section 3.1
- `price_as_of_X`: as defined in Section 3.2

### 3.4 Manual Tracking Mode

Assets with `tracking_mode = manual` cannot be priced from market data. Instead, the user states the **total position value** at a point in time (UC-45). These values live in the `manual_values` snapshot ledger, keyed by `effective_date` — the manual-mode analog of the `prices` table and of `balance_snapshots`.

- **Current value** = the latest `manual_values.value` for the asset (highest `effective_date`). If the ledger is empty, fall back to the legacy `current_value_manual` column (pre-ledger data).
- **Value at date X** = the `manual_values.value` with the largest `effective_date <= X` (`get_manual_value_as_of`). This applies to historical calculations too — the override is NOT limited to the current point-in-time dashboard.
- Buy/sell activity for the asset is tracked independently in `transactions` (UC-08/UC-09, including DCA contributions). Quantity and cost basis are unaffected by valuations.
- If a manual asset has no valuation as of date X, it contributes nothing to that date (a `price_source` of `manual` with no `price_as_of`).
- `value` is in the asset's native currency (from `market_assets.currency_code`).

The effective date of a valuation is user-selectable (default today), and revaluing on a date that already has a snapshot **replaces** that date's entry (UPSERT on `(portfolio_asset_id, effective_date)`) rather than adding a duplicate.

---

## 4. Holdings by Entity at Date X

The total holding value for a specific `entity` at `date X` is:

```text
entity_holding = cash_component + asset_component
```text

- `cash_component`: sum of cash balances (Section 2.1) across all currencies for this `entity` at `date X`.
- `asset_component`: sum of `asset_value` (Section 3.3) for all portfolio assets whose primary entity is this `entity`, where primary entity is determined by the earliest transaction for that asset.

This calculation is used by the By Entity allocation chart and the Asset Class × Entity Summary cross-tab table.

---

## 5. Total Portfolio Value at Date X

```text
total_portfolio_value = total_asset_value + total_cash
```text

- `total_asset_value`: sum of `asset_value` (Section 3.3) for all active portfolio assets at `date X`.
- `total_cash`: Total Cash at `date X` (Section 2.2).

This is the value displayed in the Historical Portfolio Value chart on the dashboard.

---

## 6. Total Return

Total return measures the overall gain or loss of the portfolio.

```text
total_return = total_investments_value + total_cash - total_invested
return_pct   = (total_return / total_invested) × 100    [or 0 if total_invested = 0]
```text

- `total_investments_value`: sum of `asset_value` (Section 3.3) for all current investment assets (excludes cash).
- `total_cash`: Total Cash across all entities (Section 2.2).
- `total_invested`: sum of `total_value` for all `INVESTMENT_BUY` transactions (total cost basis).

> ⚠️ Note: `total_investments_value` here refers only to investment assets and explicitly excludes cash. This is distinct from `total_portfolio_value` (Section 5), which includes cash.

---

## 7. Allocation Calculations

### 7.1 By Entity

```text
entity_allocation_pct = (entity_holding / sum_of_all_entity_holdings) × 100
```text

- `entity_holding`: as defined in Section 4.
- `sum_of_all_entity_holdings`: sum of `entity_holding` across all entities.

### 7.2 By Asset Class

```text
asset_class_allocation_pct = (asset_class_value / total_portfolio_value) × 100
```text

- `asset_class_value`: sum of `asset_value` (Section 3.3) for all portfolio assets in the class. Cash is treated as its own asset class labeled `CASH`, with value equal to `total_cash` (Section 2.2).
- `total_portfolio_value`: as defined in Section 5.

---

## 8. Balance Snapshots and Adjustment Mechanism

### Concept

Balance snapshots are user-defined anchor points that record a known cash balance for a specific `entity` and `currency` at a specific moment in time. They serve as the ground truth for cash calculations, with transactions layered on top to compute balances at any intermediate date.

### First Snapshot

When the first snapshot is created for an `entity`–`currency` pair, it establishes the initial balance. No adjustment transaction is generated.

### Auto-Snapshot on First Investment Buy

When the first `INVESTMENT_BUY` transaction is recorded for an `entity`–`currency` pair that has no prior balance snapshots and no prior `INCOME` or `BALANCE_ADJUSTMENT` transactions:

1. Auto-create a `balance_snapshot` with:
   - Same `entity_id` and `currency` as the buy transaction.
   - `timestamp` = buy transaction `timestamp - 1 day`.
   - `amount` = `total_value` of the buy transaction (the cash that must have existed before the purchase).
   - `notes` = `'Auto-created: initial cash inferred from first investment purchase'`.

This ensures that the portfolio value is correctly modeled as cash before the buy and as the asset after the buy, preserving total portfolio value across the conversion. Without this, the no-snapshot cash calculation starts from zero, producing a negative portfolio value that does not reflect reality.

### Subsequent Snapshots

When a new snapshot is created for an `entity`–`currency` pair that already has at least one prior snapshot:

1. Compute the expected balance at the new snapshot's timestamp using Section 2.1 Path A (from the previous snapshot forward).
2. Compute the `adjustment_amount = snapshot.amount - expected_balance`.
3. Auto-create a `BALANCE_ADJUSTMENT` transaction with:
   - Same `entity` and `currency` as the snapshot.
   - `timestamp = snapshot.date - 1 day`.
   - `total_value = adjustment_amount` (positive if snapshot is higher than expected, negative if lower).
   - Notes indicating it is a balance adjustment for this snapshot.

### Automatic Recalculation

When any transaction is created, updated, or deleted for an `entity`–`currency` pair that has snapshots:

1. Identify the next snapshot after the affected transaction's date.
2. If such a snapshot exists, recompute its adjustment:
   1. Recompute `expected_balance` from the previous snapshot through the updated transaction set (Section 2.1 Path A).
   2. Set `adjustment_amount = snapshot.amount - expected_balance`.
   3. Update the existing `BALANCE_ADJUSTMENT` transaction with the new `adjustment_amount`.

This ensures that the snapshot's target balance is always maintained regardless of transaction changes between snapshots.

### Deleting a Snapshot

When a snapshot is deleted, its associated `BALANCE_ADJUSTMENT` transaction is also deleted.

### Balance at Date X with Snapshots

Computing the cash balance for an `entity` and `currency` at `date X` follows Section 2.1 (Path A or Path B). For completeness:

- Path A applies when the most recent snapshot has `timestamp < date X`: start from `snapshot.amount` and apply all non-`BALANCE_ADJUSTMENT` transactions from the snapshot timestamp up to `date X - 1`, then all transactions on `date X`.
- Path B applies when a snapshot exists with `timestamp = date X`: start from `snapshot.amount` and apply all transactions on `date X`.

> ⚠️ Consistency note: "all non-BALANCE_ADJUSTMENT transactions" in Path A refers to the walk up to `date X - 1` per Section 2.1. The `BALANCE_ADJUSTMENT` on `date X - 1` is intentionally included in that walk (it is not filtered out), as it is the reconciliation entry for that snapshot interval.

### Constraints

- A snapshot cannot be created at a date where transactions already exist at or after that timestamp for the same `entity` and `currency`. This prevents ambiguity about which transactions fall before or after the snapshot anchor.
- A snapshot cannot be created at a date where a recurring schedule starts at or before that date for the same `entity` and `currency`. This prevents future scheduled transactions from conflicting with the snapshot anchor.

---

## 9. Currency Conversion

Currency conversion is applied in dashboard aggregation views to enable meaningful comparison of values across different currencies. The following views convert all values to a user-selected display currency:

- **Dashboard metric cards** (Portfolio Value, Cash Balance, Total Invested)
- **Dashboard historical chart** (Historical Portfolio Value)
- **Dashboard allocation charts** (By Entity, By Asset Class)
- **Dashboard cross-tab table** (Asset Class × Entity Summary)

### Conversion Logic

1. Collect all currencies present in holdings and cash balances.
2. For each currency (except the display currency), fetch the latest exchange rate to the display currency.
3. Multiply each value by its corresponding exchange rate before summing.
4. If no exchange rate is available for a currency, the value is included as-is (no conversion).

### Formula

```text
converted_value = native_value × rate(native_currency → display_currency)
```text

### Notes

- Exchange rates are fetched from the `currencies` table using the latest available rate.
- The system attempts both directions: `native → display` and `display → native` (inverted).
- Cash balances from balance snapshots are properly handled via the snapshot-aware calculation (Section 2).
- Non-dashboard views (e.g., Transactions, Income) do not apply currency conversion and display values in their native currencies.
- **Exception — realized P&L and invested historic (Performance page):** these follow the fiscal-rule conversion in Section 16, not the latest-rate rule in this section.

---

## 10. Cost Basis

Cost basis is required by Sections 11, 12, and 13. The system uses the **FIFO (First In, First Out)** method: when units are sold, the cost of the earliest purchased units is consumed first.

### 10.1 FIFO Lot Queue at Date X

The FIFO lot queue is an ordered list of remaining purchase lots, computed by walking all `INVESTMENT_BUY` and `INVESTMENT_SELL` transactions with `timestamp <= date X` in chronological order:

1. Start with an empty `lot_queue` (ordered list of `{ quantity, unit_cost, buy_date }` pairs).
2. For each `INVESTMENT_BUY` transaction:
   1. Append `{ quantity: transaction.quantity, unit_cost: transaction.total_value / transaction.quantity, buy_date: transaction.timestamp }` to the end of `lot_queue`.
3. For each `INVESTMENT_SELL` transaction:
   1. Set `remaining_to_consume = transaction.quantity`.
   2. While `remaining_to_consume > 0`, consume from the front of `lot_queue`:
      1. If `lot_queue.front.quantity <= remaining_to_consume`: remove the front lot entirely and subtract its quantity from `remaining_to_consume`.
      2. Otherwise: reduce `lot_queue.front.quantity` by `remaining_to_consume` and set `remaining_to_consume = 0`.

The resulting `lot_queue` represents the remaining open lots at `date X`.

> `buy_date` is retained per lot solely so rule-based display conversion (Section 16) can convert each consumed lot's cost at the rate of its own purchase date. It does not affect native cost basis (Section 10.2).

### 10.2 Cost Basis of a Position at Date X

```text
cost_basis = sum of (lot.quantity × lot.unit_cost) for all lots in lot_queue
```text

- `lot_queue`: as defined in Section 10.1 at `date X`.

---

## 11. Realized Gains/Losses

Realized gain/loss is the profit or loss locked in by `INVESTMENT_SELL` transactions, relative to the FIFO cost of the specific lots consumed by each sale (Section 10.1).

> The FIFO walk (Sections 10.1/11.1) processes **all** buy/sell transactions regardless of `portfolio_assets.is_active`: sells of deactivated ("closed") assets keep contributing to historical P&L. Only current-state views (holdings, valuation, allocation) exclude inactive assets.

### 11.1 Per Sale Transaction

For each `INVESTMENT_SELL` transaction at timestamp `T`, the realized gain is computed by consuming lots from the FIFO queue as it stood just before `T`:

1. Compute `lot_queue` (Section 10.1) using all transactions with `timestamp < T`.
2. Set `remaining_to_consume = transaction.quantity`, `cost_of_sold_units = 0`.
3. Consume from the front of `lot_queue` until `remaining_to_consume = 0`:
   1. `consumed = min(lot_queue.front.quantity, remaining_to_consume)`
   2. `cost_of_sold_units += consumed × lot_queue.front.unit_cost`
   3. Reduce `lot_queue.front.quantity` by `consumed` (remove lot if fully consumed).
   4. `remaining_to_consume -= consumed`

```text
realized_gain_per_sale = proceeds - cost_of_sold_units
```text

- `proceeds`: `transaction.total_value` for this `INVESTMENT_SELL`.

### 11.2 Cumulative Realized Gain/Loss at Date X

```text
total_realized_gain = sum of realized_gain_per_sale for all INVESTMENT_SELL transactions with timestamp <= date X
```

### 11.3 Realized P&L Percentage

Realized P&L as a percentage of the cost basis of the **sold** units — the strict analog of Section 12.1, which divides by the cost basis of held shares:

```text
realized_pl_pct = total_realized_gain / sold_cost_basis × 100    [0 if sold_cost_basis = 0]
```

- `total_realized_gain`: as defined in Section 11.2.
- `sold_cost_basis`: Σ over all sells of the cost of the lots each sale consumed (Section 11.1).

In display currency, both numerator and denominator convert under the same per-sale fiscal rule (Section 16), so the percentage is conversion-invariant.

---

## 12. Unrealized Gains/Losses

Unrealized gain/loss represents the current paper profit or loss on open positions.

```text
unrealized_gain = asset_value - cost_basis
```

- `asset_value`: as defined in Section 3.3, at the current `date X`.
- `cost_basis`: as defined in Section 10.2, at `date X`.

Only portfolio assets with `net_quantity > 0` have an unrealized gain/loss.

### 12.1 Unrealized P&L Percentage

```text
unrealized_pl_pct = total_unrealized_gain / total_cost_basis × 100    [0 if total_cost_basis = 0]
```

- `total_unrealized_gain`: Σ of Section 12 across open positions.
- `total_cost_basis`: Σ of Section 10.2 across the same open positions (FIFO remaining-lot cost).

---

## 13. Per Portfolio Asset P&L

Per-portfolio-asset P&L combines all sources of profit and loss for a single portfolio asset.

```text
total_pnl = unrealized_gain + total_realized_gain
```text

- `unrealized_gain`: as defined in Section 12.
- `total_realized_gain`: as defined in Section 11.2.

> Note: Dividends received from an asset are not included here by default, as they are already reflected in the cash balance. If a dividend-inclusive P&L view is needed, add the sum of `total_value` for all transactions linked to this asset with `income_category = 'dividends'`.

---

## 14. Dividend Yield

Two yield definitions are supported, applicable per asset at `date X`.

### 14.1 Trailing Yield (yield on current value)

```text
trailing_yield = total_dividends_received / asset_value × 100
```text

- `total_dividends_received`: sum of `total_value` for all transactions linked to this asset with `income_category = 'dividends'` and `timestamp <= date X`.
- `asset_value`: as defined in Section 3.3.

### 14.2 Yield on Cost

```text
yield_on_cost = total_dividends_received / total_invested_in_asset × 100
```text

- `total_dividends_received`: same as Section 14.1.
- `total_invested_in_asset`: sum of `total_value` for all `INVESTMENT_BUY` transactions for this asset with `timestamp <= date X`.

---

## 15. Currency Exposure Summary

The currency exposure summary aggregates the portfolio's value broken down by currency, without conversion. It answers: how much of the portfolio is denominated in each currency?

### 15.1 Cash Exposure per Currency

For each `currency` present in any `entity`–`currency` pair:

```text
cash_exposure[currency] = sum of cash_balance (Section 2.1) across all entities for this currency at date X
```text

### 15.2 Asset Exposure per Currency

Each asset is assumed to be denominated in a single `asset.currency`. For each such currency:

```text
asset_exposure[currency] = sum of asset_value (Section 3.3) for all assets with asset.currency = currency at date X
```text

### 15.3 Total Exposure per Currency

```text
total_exposure[currency] = cash_exposure[currency] + asset_exposure[currency]
```text

### 15.4 Exposure as a Percentage

```text
exposure_pct[currency] = (total_exposure[currency] / sum_of_all_total_exposure) × 100
```text

- `sum_of_all_total_exposure`: sum of `total_exposure[currency]` across all currencies. Note that this sum mixes currencies and is only meaningful as a denominator for percentage allocation, not as an absolute monetary figure.

---

## 16. P&L Display-Currency Conversion (Fiscal Rules)

*Implemented (Phases 1–2 of `doc/plans/fiscal_rules_pnl_engine.md`): true FIFO lots, the `PnlRule` registry, proceeds-currency handling, buy-date invested-historic conversion, rate-fallback flags, and rule assignment over time via `fiscal_periods` with a `transactions.fiscal_rule` snapshot. The rule applied to a sell is its frozen snapshot, or the locale-inferred default when no period matched.*

### 16.1 Native P&L (rule-independent)

Every rule consumes the same **native** realized gain per sell (Section 11.1), computed from true FIFO lots:

```text
native_gain = sell_total − cost_basis
```

- `sell_total`: `transaction.total_value` of the `INVESTMENT_SELL`, in the asset's `currency`.
- `cost_basis`: sum of the consumed lots' cost (Section 10.1/11.1), in the asset's `currency`.

Native P&L never depends on the rule — rules only define the display-currency conversion. The realized-gains table therefore always shows native values.

### 16.2 Rule Set

The rule applied to a sell is the one active on its **sell date** (resolved via `fiscal_periods`, UC-47) and frozen onto the transaction at creation (`transactions.fiscal_rule`). With no configured period, the rule is inferred from the user's locale (fallback `default`).

| key | Name | Display conversion of a sell at date `T` |
|-----|------|------------------------------------------|
| `spain` | Spain (constant sale-day rate) | `native_gain × rate(asset→display, T)` |
| `japan` | Japan (FX-aware) | `sell_total × rate(asset→display, T) − Σ lot_cost × rate(asset→display, lot.buy_date)` over consumed lots |
| `default` | Default (copy of `spain`) | same as `spain` |
| `latest` | Legacy / current behavior | `native_gain × latest available rate` |
| `none` | No rule | same as `default` (Spain copy) |

When the sell records `payment_currency` + `fx_rate`, proceeds are realized in `payment_currency`:

```text
proceeds = sell_total × fx_rate                    (in payment_currency)
proceeds_in_display = proceeds × rate(payment_currency → display, T)
```

An empty `payment_currency` means proceeds stay in the asset `currency` (converted as in the table above).

### 16.3 Invested Historic (buy-side conversion)

`total_invested_historic` is about invested cash only — it is rule-independent and always buy-date converted:

```text
total_invested_historic = Σ over INVESTMENT_BUY transactions of
    buy_total × rate(buy.currency → display, buy.timestamp)
```

### 16.4 Rate Lookup and Fallback

- Historical rates come from the `currencies` table (Section 9), looked up as of the required date.
- If no rate exists for the exact date, the **closest available rate in time** is used, the response flags the fallback, and the UI warns the user to provide the manual rate for accuracy.
- If no rate exists at all for a currency, the value is included unconverted (as in Section 9) and flagged.

---

## 17. Taxable P&L and Tax Computation (Tax Page)

Phase 3 implemented the taxable P&L view (§17.1–§17.5). Phase 4 extends with tax computation, confirmed-vs-computed resolution, user-editable rates, and per-item drill-down (§17.6–§17.13). See `doc/plans/tax_page.md`.

### 17.1 Ruleset extension

A ruleset now bundles the realized-gains conversion (Section 16.2), a **fiscal-year start** `(month, day)`, and **dividend** treatment. v1 uses the natural year `(1, 1)` for all rulesets; the field is configurable. Dividends are taxable income, not sells, and convert at their `payment_date` (fallback `timestamp`) rate — independent of the sell-conversion rules.

### 17.2 Realized gains

Per sell, the taxable amount is the rule-converted value (Section 16.2) under the sell's frozen `fiscal_rule`, then reduced by any linked exemption (Section 17.4). Losses pass through unchanged.

### 17.3 Dividends

```text
dividend_taxable = dividend.total_value × rate(dividend.currency → display, payment_date)
```

Using the closest-in-time rate with fallback flags (Section 16.4).

### 17.4 Exemption

A transaction linked to `fiscal_exemption_id` reduces its positive taxable amount `g`:

```text
rate_exempt = g × exemption_rate / 100          (capped by exemption_rate_limit when set)
fixed       = exemption_amount × rate(currency → display, tx date)
taxable     = g − min(g, rate_exempt + fixed)
```

Losses are never reduced by an exemption.

### 17.5 Fiscal-year grouping

Each taxable item is grouped into the fiscal year of the **report ruleset** (the `ruleset` query param, default = locale-derived). A date before the fiscal-year start belongs to the previous fiscal year.

### 17.6 Tax categories

Extensible enum of taxable income types. v1 implements `capital_gains` and `dividends`; `salary`, `interest`, and `other` are reserved for future use.

| Category | Description |
|---|---|
| `capital_gains` | Realized gains from investment sells. |
| `dividends` | Dividend income. |
| `salary` | Reserved: work income (future aggregation). |
| `interest` | Reserved: interest income. |
| `other` | Reserved: catch-all. |

### 17.7 Tax model

Tax computation is split into two layers:

- **Model structure** (code): a per-ruleset `TaxModel` that defines how categories combine, whether brackets are progressive, and how the base is split. Registered in a `TAX_MODELS` dict.
- **Tax parameters** (data): rates and brackets stored in the `tax_rates` table, user-editable per ruleset/category/year.

v1 models:

| Model | Rulesets | Behavior |
|---|---|---|
| `SavingsCombined` | `spain`, `default` | Gains + dividends share one progressive bracket table. Combined base = sum of post-exemption category bases. Tax computed on combined total; split proportionally back to categories. |
| `FlatPerCategory` | `japan`, `latest`, `none` | Flat rate per category, no combining. Each category taxed independently. |

### 17.8 Tax rates (data)

Stored in the `tax_rates` table: `ruleset_key`, `category`, `from_amount`, `to_amount`, `rate`, `year_start`.

- **Flat rate**: one row per category (`from_amount = 0`, `to_amount = NULL`).
- **Progressive brackets**: multiple rows per category with ascending `from_amount` bands, each with its own `rate`. `to_amount = NULL` = unbounded top bracket.
- **Year-specific**: `year_start` allows different rates per tax year; `NULL` = default/fallback for all years.
- **Profile-scoped**: optional `profile_id` for per-profile rate overrides.

Seeded values (migration 013):

| Ruleset | Category | Brackets |
|---|---|---|
| `spain` | `capital_gains` | 19% (€0–6k), 21% (€6k–50k), 23% (€50k+) |
| `spain` | `dividends` | Same progressive bands (shared savings income base) |
| `japan` | `capital_gains` | Flat 20.315% |
| `japan` | `dividends` | Flat 20.315% |
| `default` | `capital_gains` | Copy of Spain |
| `default` | `dividends` | Copy of Spain |
| `latest` / `none` | — | No rates seeded |

### 17.9 Computed tax

Per fiscal year, the engine:

1. Collects `bases[category]` = post-exemption taxable base (from §17.2–§17.4).
2. Loads brackets from `tax_rates` for the resolved ruleset and year.
3. Selects the `TaxModel` from the `TAX_MODELS` registry.
4. Calls `model.compute(bases, brackets)` → `TaxResult { tax_owed, total_tax_owed, combined_base }`.

#### SavingsCombined

```text
combined_base = Σ bases[category]
total_tax     = apply_progressive(combined_base, brackets)
tax_owed[category] = total_tax × (bases[category] / combined_base)   # proportional split
```

If `combined_base = 0`, all `tax_owed` are 0.

`apply_progressive(base, brackets)` walks brackets in ascending `from_amount` order: for each bracket, the portion of `base` within `[from_amount, to_amount)` is taxed at that bracket's `rate`.

#### FlatPerCategory

```text
tax_owed[category] = bases[category] × bracket[category].rate
total_tax_owed     = Σ tax_owed[category]
```

### 17.10 Confirmed tax

Actual tax paid is stored per transaction in `transaction_taxes`. The `tax_type` field uses a formalized vocabulary:

| `tax_type` | Maps to category | Notes |
|---|---|---|
| `capital_gains` | `capital_gains` | Tax on realized gains. |
| `dividends` | `dividends` | Tax on dividend income. |
| `withholding` | `dividends` | Dividend withholding (maps to dividends). |
| `stamp_duty` | `capital_gains` | Stamp duty on sells (maps to capital gains). |
| `other` | — | Catch-all. |

Confirmed tax per category per fiscal year = sum of `transaction_taxes.tax_amount` for transactions of that category in that year.

### 17.11 Tax resolution

Per item, one value:

```text
tax    = confirmed_tax if present else computed_tax
source = "confirmed" if present else "computed"
```

This mirrors the app's existing auto-derive pattern (`net_amount` derived from `gross_amount × fx_rate`; `total_value` derived from `quantity × unit_price`). One field, either entered or derived.

### 17.12 Per-item detail

The response includes an `items[]` list per fiscal year:

| Field | Type | Description |
|---|---|---|
| `kind` | `"sell"` or `"dividend"` | Transaction type. |
| `transaction_id` | int | FK to `transactions`. |
| `instrument` | string or null | Ticker / name. |
| `date` | date | Sell date or dividend payment date. |
| `taxable_amount` | float | Post-exemption taxable amount in display currency. |
| `rule` | string | Frozen `fiscal_rule` (sells) or resolved ruleset (dividends). |
| `tax_owed` | float or null | Computed tax from brackets (null if no rates). |
| `confirmed_tax` | float or null | User-entered tax from `transaction_taxes`. |
| `source` | `"computed"` or `"confirmed"` | Which value resolves. |

Items are sorted by date within each fiscal year.

### 17.13 Profile default ruleset

`profiles.default_fiscal_rule` (nullable) overrides the locale-inferred default. Resolution order:

1. `fiscal_periods` containing the sell date → period's `rule_key`.
2. `profiles.default_fiscal_rule` (if set).
3. Locale inference: `es` → `spain`, `ja` → `japan`, else `default`.

Displayed in Settings (read + edit) and on the Tax page header.

---

## Appendix: Calculations Not Currently Defined

The following calculations are common in financial portfolio applications and are not yet specified in this document. They may warrant future definition:

- **Time-weighted return (TWR)** — return metric that neutralizes the effect of cash flows; standard for fund performance comparison.
- **Money-weighted return (IRR)** — return metric that accounts for the timing and size of cash flows; reflects investor experience.
