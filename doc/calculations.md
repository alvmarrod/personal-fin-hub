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
  - [12. Unrealized Gains/Losses](#12-unrealized-gainslosses)
  - [13. Per-Asset P\&L](#13-per-asset-pl)
  - [14. Dividend Yield](#14-dividend-yield)
    - [14.1 Trailing Yield (yield on current value)](#141-trailing-yield-yield-on-current-value)
    - [14.2 Yield on Cost](#142-yield-on-cost)
  - [15. Currency Exposure Summary](#15-currency-exposure-summary)
    - [15.1 Cash Exposure per Currency](#151-cash-exposure-per-currency)
    - [15.2 Asset Exposure per Currency](#152-asset-exposure-per-currency)
    - [15.3 Total Exposure per Currency](#153-total-exposure-per-currency)
    - [15.4 Exposure as a Percentage](#154-exposure-as-a-percentage)
  - [Appendix: Calculations Not Currently Defined](#appendix-calculations-not-currently-defined)

---

## 1. Transaction Types and Cash Impact

Every transaction has a type that determines its effect on cash balance.

| Type | Cash Impact | Description |
| ---- | ----------- | ----------- |
| MONEY_IN | Positive | External cash deposit into an entity |
| MONEY_OUT | Negative | External cash withdrawal from an entity |
| INVESTMENT_BUY | Negative | Cash spent to acquire assets |
| INVESTMENT_SELL | Positive | Cash received from selling assets |
| DIVIDEND | Positive | Dividend income received as cash |
| INTEREST | Positive | Interest income received as cash |
| TRANSFER | Neutral | Movement of funds between entities; excluded from cash flow sums |
| BALANCE_ADJUSTMENT | Excluded | System-generated reconciliation entry; explicitly filtered out of all cash flow calculations |

The canonical cash impact for any transaction on `total_value` is:

- Add `total_value` if type is `MONEY_IN`, `INTEREST`, `DIVIDEND`, or `INVESTMENT_SELL`.
- Subtract `total_value` if type is `MONEY_OUT` or `INVESTMENT_BUY`.
- No effect otherwise.

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

Only assets with `net_quantity > 0` are included in valuation.

### 3.2 Price Lookup

The `price_as_of_X` for an asset at `date X` is the most recent entry in the prices table with `timestamp <= date X`. If multiple prices exist, the one with the latest timestamp at or before `date X` is selected. If no price exists at or before `date X`, the asset contributes zero value.

### 3.3 Asset Value

```
asset_value = net_quantity × price_as_of_X
```

- `net_quantity`: as defined in Section 3.1
- `price_as_of_X`: as defined in Section 3.2

### 3.4 Manual Tracking Mode

For the current point-in-time dashboard only, assets with `tracking_mode = manual` and a non-null `current_value_manual` use that value directly instead of the Section 3.3 calculation. This override does not apply to historical calculations.

---

## 4. Holdings by Entity at Date X

The total holding value for a specific `entity` at `date X` is:

```
entity_holding = cash_component + asset_component
```

- `cash_component`: sum of cash balances (Section 2.1) across all currencies for this `entity` at `date X`.
- `asset_component`: sum of `asset_value` (Section 3.3) for all portfolio assets whose primary entity is this `entity`, where primary entity is determined by the earliest transaction for that asset.

This calculation is used by the By Entity allocation chart and the Asset Class × Entity Summary cross-tab table.

---

## 5. Total Portfolio Value at Date X

```
total_portfolio_value = total_asset_value + total_cash
```

- `total_asset_value`: sum of `asset_value` (Section 3.3) for all active portfolio assets at `date X`.
- `total_cash`: Total Cash at `date X` (Section 2.2).

This is the value displayed in the Historical Portfolio Value chart on the dashboard.

---

## 6. Total Return

Total return measures the overall gain or loss of the portfolio.

```
total_return = total_investments_value + total_cash - total_invested
return_pct   = (total_return / total_invested) × 100    [or 0 if total_invested = 0]
```

- `total_investments_value`: sum of `asset_value` (Section 3.3) for all current investment assets (excludes cash).
- `total_cash`: Total Cash across all entities (Section 2.2).
- `total_invested`: sum of `total_value` for all `INVESTMENT_BUY` transactions (total cost basis).

> ⚠️ Note: `total_investments_value` here refers only to investment assets and explicitly excludes cash. This is distinct from `total_portfolio_value` (Section 5), which includes cash.

---

## 7. Allocation Calculations

### 7.1 By Entity

```
entity_allocation_pct = (entity_holding / sum_of_all_entity_holdings) × 100
```

- `entity_holding`: as defined in Section 4.
- `sum_of_all_entity_holdings`: sum of `entity_holding` across all entities.

### 7.2 By Asset Class

```
asset_class_allocation_pct = (asset_class_value / total_portfolio_value) × 100
```

- `asset_class_value`: sum of `asset_value` (Section 3.3) for all assets in the class. Cash is treated as its own asset class labeled `CASH`, with value equal to `total_cash` (Section 2.2).
- `total_portfolio_value`: as defined in Section 5.

---

## 8. Balance Snapshots and Adjustment Mechanism

### Concept

Balance snapshots are user-defined anchor points that record a known cash balance for a specific `entity` and `currency` at a specific moment in time. They serve as the ground truth for cash calculations, with transactions layered on top to compute balances at any intermediate date.

### First Snapshot

When the first snapshot is created for an `entity`–`currency` pair, it establishes the initial balance. No adjustment transaction is generated.

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

```
converted_value = native_value × rate(native_currency → display_currency)
```

### Notes

- Exchange rates are fetched from the `currencies` table using the latest available rate.
- The system attempts both directions: `native → display` and `display → native` (inverted).
- Cash balances from balance snapshots are properly handled via the snapshot-aware calculation (Section 2).
- Non-dashboard views (e.g., Transactions, Income) do not apply currency conversion and display values in their native currencies.

---

## 10. Cost Basis

Cost basis is required by Sections 11, 12, and 13. The system uses the **FIFO (First In, First Out)** method: when units are sold, the cost of the earliest purchased units is consumed first.

### 10.1 FIFO Lot Queue at Date X

The FIFO lot queue is an ordered list of remaining purchase lots, computed by walking all `INVESTMENT_BUY` and `INVESTMENT_SELL` transactions with `timestamp <= date X` in chronological order:

1. Start with an empty `lot_queue` (ordered list of `{ quantity, unit_cost }` pairs).
2. For each `INVESTMENT_BUY` transaction:
   1. Append `{ quantity: transaction.quantity, unit_cost: transaction.total_value / transaction.quantity }` to the end of `lot_queue`.
3. For each `INVESTMENT_SELL` transaction:
   1. Set `remaining_to_consume = transaction.quantity`.
   2. While `remaining_to_consume > 0`, consume from the front of `lot_queue`:
      1. If `lot_queue.front.quantity <= remaining_to_consume`: remove the front lot entirely and subtract its quantity from `remaining_to_consume`.
      2. Otherwise: reduce `lot_queue.front.quantity` by `remaining_to_consume` and set `remaining_to_consume = 0`.

The resulting `lot_queue` represents the remaining open lots at `date X`.

### 10.2 Cost Basis of a Position at Date X

```
cost_basis = sum of (lot.quantity × lot.unit_cost) for all lots in lot_queue
```

- `lot_queue`: as defined in Section 10.1 at `date X`.

---

## 11. Realized Gains/Losses

Realized gain/loss is the profit or loss locked in by `INVESTMENT_SELL` transactions, relative to the average cost at the time of each sale.

### 11.1 Per Sale Transaction

For each `INVESTMENT_SELL` transaction at timestamp `T`, the realized gain is computed by consuming lots from the FIFO queue as it stood just before `T`:

1. Compute `lot_queue` (Section 10.1) using all transactions with `timestamp < T`.
2. Set `remaining_to_consume = transaction.quantity`, `cost_of_sold_units = 0`.
3. Consume from the front of `lot_queue` until `remaining_to_consume = 0`:
   1. `consumed = min(lot_queue.front.quantity, remaining_to_consume)`
   2. `cost_of_sold_units += consumed × lot_queue.front.unit_cost`
   3. Reduce `lot_queue.front.quantity` by `consumed` (remove lot if fully consumed).
   4. `remaining_to_consume -= consumed`

```
realized_gain_per_sale = proceeds - cost_of_sold_units
```

- `proceeds`: `transaction.total_value` for this `INVESTMENT_SELL`.

### 11.2 Cumulative Realized Gain/Loss at Date X

```
total_realized_gain = sum of realized_gain_per_sale for all INVESTMENT_SELL transactions with timestamp <= date X
```

---

## 12. Unrealized Gains/Losses

Unrealized gain/loss represents the current paper profit or loss on open positions.

```
unrealized_gain = asset_value - cost_basis
```

- `asset_value`: as defined in Section 3.3, at the current `date X`.
- `cost_basis`: as defined in Section 10.2, at `date X`.

Only assets with `net_quantity > 0` have an unrealized gain/loss.

---

## 13. Per-Asset P&L

Per-asset P&L combines all sources of profit and loss for a single asset.

```
total_pnl = unrealized_gain + total_realized_gain
```

- `unrealized_gain`: as defined in Section 12.
- `total_realized_gain`: as defined in Section 11.2.

> Note: Dividends received from an asset are not included here by default, as they are already reflected in the cash balance. If a dividend-inclusive P&L view is needed, add the sum of `total_value` for all `DIVIDEND` transactions linked to this asset.

---

## 14. Dividend Yield

Two yield definitions are supported, applicable per asset at `date X`.

### 14.1 Trailing Yield (yield on current value)

```
trailing_yield = total_dividends_received / asset_value × 100
```

- `total_dividends_received`: sum of `total_value` for all `DIVIDEND` transactions linked to this asset with `timestamp <= date X`.
- `asset_value`: as defined in Section 3.3.

### 14.2 Yield on Cost

```
yield_on_cost = total_dividends_received / total_invested_in_asset × 100
```

- `total_dividends_received`: same as Section 14.1.
- `total_invested_in_asset`: sum of `total_value` for all `INVESTMENT_BUY` transactions for this asset with `timestamp <= date X`.

---

## 15. Currency Exposure Summary

The currency exposure summary aggregates the portfolio's value broken down by currency, without conversion. It answers: how much of the portfolio is denominated in each currency?

### 15.1 Cash Exposure per Currency

For each `currency` present in any `entity`–`currency` pair:

```
cash_exposure[currency] = sum of cash_balance (Section 2.1) across all entities for this currency at date X
```

### 15.2 Asset Exposure per Currency

Each asset is assumed to be denominated in a single `asset.currency`. For each such currency:

```
asset_exposure[currency] = sum of asset_value (Section 3.3) for all assets with asset.currency = currency at date X
```

### 15.3 Total Exposure per Currency

```
total_exposure[currency] = cash_exposure[currency] + asset_exposure[currency]
```

### 15.4 Exposure as a Percentage

```
exposure_pct[currency] = (total_exposure[currency] / sum_of_all_total_exposure) × 100
```

- `sum_of_all_total_exposure`: sum of `total_exposure[currency]` across all currencies. Note that this sum mixes currencies and is only meaningful as a denominator for percentage allocation, not as an absolute monetary figure.

---

## Appendix: Calculations Not Currently Defined

The following calculations are common in financial portfolio applications and are not yet specified in this document. They may warrant future definition:

- **Time-weighted return (TWR)** — return metric that neutralizes the effect of cash flows; standard for fund performance comparison.
- **Money-weighted return (IRR)** — return metric that accounts for the timing and size of cash flows; reflects investor experience.
