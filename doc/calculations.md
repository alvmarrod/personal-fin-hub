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
    - [The Reconciliation Model](#the-reconciliation-model)
    - [Every Snapshot Has an Adjustment](#every-snapshot-has-an-adjustment)
    - [Inferred Cash (Injection)](#inferred-cash-injection)
    - [Automatic Recalculation](#automatic-recalculation)
    - [Deleting a Snapshot](#deleting-a-snapshot)
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
    - [14.3 Portfolio Dividend Yield (on Invested Historic)](#143-portfolio-dividend-yield-on-invested-historic)
    - [14.4 Per-Asset Yields in Display Currency](#144-per-asset-yields-in-display-currency)
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

The canonical cash impact for any transaction on its **cash pocket currency** (`COALESCE(payment_currency, currency)`) is:

- Add `COALESCE(gross_amount, total_value)` if type is `INCOME`, `INVESTMENT_SELL`, or `TRANSFER_IN`.
- Subtract `COALESCE(gross_amount, total_value)` if type is `MONEY_OUT`, `INVESTMENT_BUY`, or `TRANSFER_OUT`.
- Add `total_value` (already signed) if type is `BALANCE_ADJUSTMENT` — an adjustment is a real cash movement; positive adds cash, negative removes it.
- No effect for the reserved `TRANSFER` value.

When `payment_currency` differs from `currency` (cross-currency trades), `gross_amount` = `total_value × fx_rate` — the amount in the payment currency. Cash flows into the payment-currency pocket, not the asset-currency pocket. An empty `payment_currency` means the cash stays in the asset `currency` (fallback to `total_value`).

Income/expense analytics (Cash Flow, Income by Source) sum only `INCOME`/`INVESTMENT_SELL` as inflows and `MONEY_OUT`/`INVESTMENT_BUY` as outflows — `TRANSFER_IN`/`TRANSFER_OUT` are never counted as income or expense.

---

## 2. Cash Balance at Date X

### 2.1 Per Entity and Cash Pocket

The cash balance for a specific `entity` and **cash pocket** at a given `date X` is the **actual balance**. A cash pocket is identified by `COALESCE(payment_currency, currency)` — the currency in which the cash actually lands (the payment currency for cross-currency trades, the asset currency otherwise).

```text
actual_balance(X) = base(X) + Σ(transactions t where base(X).timestamp ≤ t.timestamp < X)
```

- `base(X)` is the most recent `balance_snapshot` for this `entity`–`cash_pocket` pair with `timestamp < X`; its `amount` is the base. If no such snapshot exists, `base(X) = 0` and the sum runs from the origin of the pair.
- Every transaction applies its signed cash impact (Section 1) in its cash pocket currency. `BALANCE_ADJUSTMENT` applies its signed `total_value`.
- The reference is always the snapshot **strictly before** `X`. A snapshot dated exactly on `X` therefore anchors dates *after* `X` (its `amount` becomes the base for any later date); it does not retroactively change the balance *at* `X`, which already includes the reconciliation adjustment that lands on it (Section 8).

For reconciliation (Section 8) the system additionally computes the **computed balance**:

```text
computed_balance(X) = actual_balance(X) computed while excluding the snapshot's own BALANCE_ADJUSTMENT
```

This internal quantity differs from `actual_balance` only by the snapshot's own `BALANCE_ADJUSTMENT` (identified via its `balance_snapshot_id`). It is used **only** to derive/refresh adjustments; all read paths (cards, charts, analytics) use `actual_balance`.

### 2.2 Total Cash at Date X

The system-wide cash balance at `date X` is the sum of all per-entity-per-cash-pocket balances (Section 2.1) across all `entity`–`cash_pocket` pairs.

### 2.3 Total Cash at Date X in Currency Y

1. Compute `Total Cash at Date X` (Section 2.2), which is broken down at `entity`–`cash_pocket` level.
2. For each `entity`–`cash_pocket` pair where the cash pocket differs from `currency Y`, apply the exchange rate for `date X - 1`.
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

A portfolio asset may hold positions at more than one entity. Its value splits across those entities by each entity's own transactions, not by a single primary entity.

The total holding value for a specific `entity` at `date X` is:

```text
entity_holding = cash_component + asset_component
```text

- `cash_component`: sum of cash balances (Section 2.1) across all cash pockets for this `entity` at `date X`.
- `asset_component`: sum over each asset of `entity_asset_value`, where `entity_asset_value = entity_net_quantity × price_as_of_X`. `entity_net_quantity` is the sum of `INVESTMENT_BUY` quantities minus the sum of `INVESTMENT_SELL` quantities for that `(asset, entity)` pair with `timestamp <= date X` (Section 3.1 applied per entity).

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

**Performance page variant** (`GET /analytics/performance`, display currency): investment-performance focused and computed server-side.

```text
total_return = realized_pl_trading + total_dividends
total_return_pct = total_return / invested_historic × 100    [or 0 if invested_historic = 0]
```

- `realized_pl_trading`: Section 11 (per-entity FIFO buy/sell P&L) converted per sale under its frozen fiscal rule (Section 16.2). Dividends are **not** part of this component.
- `total_dividends`: all-time dividend payments (Section 14.3), each converted at its own payment-date rate.
- `invested_historic`: buy-side cash invested, per-buy purchase-date rates (Section 16.3).

> Unrealized P&L (Section 12) is **not** part of Total Return; it is reported separately as `total_unrealized_pl` and visualized in the Portfolio band. Interest is excluded (cash yield) and reported separately as `total_interest`.

- Interest is deliberately **excluded**: it accrues from holding cash, not from investment decisions.

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

Balance snapshots are user-defined anchor points that record a known cash balance for a specific `entity` and **cash pocket** (`COALESCE(payment_currency, currency)`) at a specific moment in time. They are the ground truth for cash: a snapshot's `amount` is the target balance at its `timestamp`, and every `BALANCE_ADJUSTMENT` transaction exists to reconcile the gap between what the recorded transactions imply (`computed_balance`) and that target.

### The Reconciliation Model

For a snapshot `S` with `timestamp = ts` and `amount = target`:

```text
computed = computed_balance(ts)          # Σ transactions in the interval, EXCLUDING S's own adjustment
adjustment = target − computed
actual_balance(ts) = computed + adjustment == target
```

- `computed_balance(ts)` is the balance built from `base(ts)` (the prior snapshot, or 0) plus every transaction in the interval **except** `S`'s own `BALANCE_ADJUSTMENT`. Excluding it is what makes the computation non-circular (otherwise the adjustment would always recompute to 0).
- The adjustment is a single signed `BALANCE_ADJUSTMENT` transaction placed at `ts − 1 day at 23:59:59` — the last moment before the snapshot — so it is the final event of the interval and `actual_balance` lands exactly on `target` at the snapshot.
- The snapshot's own adjustment is linked to it via `transactions.balance_snapshot_id = S.id`. Injected (standalone) adjustments leave that column `NULL` and instead attach to the spends they fund via `balance_adjustment_links` (see *Attachment Model* below).

### Every Snapshot Has an Adjustment

When a snapshot is created, the system always ensures its reconciliation adjustment exists:

- **First snapshot** (no prior snapshot for the pair): `computed = Σ` all transactions up to `ts` (from origin), and `adjustment = target − computed`. There is no prior reference to walk from, but the same rule applies — the first snapshot gets its own adjustment exactly like any other.
- **Subsequent snapshot**: `computed` is built from the prior snapshot forward (Section 2.1).

### Inferred Cash (Injection)

A **spend** (`INVESTMENT_BUY`, `MONEY_OUT`, `TRANSFER_OUT`) that would otherwise be unexplained — typically because no earlier snapshot or income establishes the funds — can be paired with an injected `BALANCE_ADJUSTMENT` immediately before it (at `spend.date − 1 day at 23:59:59`, `balance_snapshot_id = NULL`). This records the cash that must have existed to fund the spend without a snapshot anchor. The injection is a real signed cash transaction and is therefore included in `actual_balance`.

**Cash pocket and amount**: the injection targets the spend's **cash pocket** (`COALESCE(payment_currency, currency)`):

- **Same-currency spend** (`payment_currency` is NULL): inject into the `currency` pocket with `total_value` equal to the spend's `total_value`.
- **Cross-currency spend** (`payment_currency` is set): inject into the `payment_currency` pocket with `total_value` equal to `gross_amount` (i.e. `total_value × fx_rate`, the amount in the account currency). The cash is then spent from the payment-currency pocket to fund the asset purchase.

The choice between *inject* and *let the balance change* (debit the known balance) is offered for every spend; the default is chosen per operation:

- spend with a prior snapshot (or sufficient recorded balance) → **debit** the balance (no injection);
- spend with no prior reference that would drive the pair negative → **inject** inferred cash;
- inflows (`INCOME`, `INVESTMENT_SELL`, `TRANSFER_IN`) → always add to the balance; no injection concept.

Deviating from the default is allowed and surfaced with a confirmation warning. The chosen handling is **persisted** on the spend as `cash_handling` (`'inject'` | `'debit'`; `NULL` = smart default decided at record time), so every transaction carries a durable record of how its cash impact was reconciled and later passes can honor the original intent instead of re-deriving it.

### Fees and Taxes as Cash Movements

Fees (`transaction_fees`) and taxes (`transaction_taxes`) are real cash-outs, not metadata. Each row moves the balance of its **parent transaction's entity**, charged to that entity's **main pocket**:

```text
fee_cash_out = compute_fee(nature, fixed_amount, percentage, tx.total_value)
target_pair  = (tx.entity_id, entity.main_currency)
balance(main pocket, t) -= Σ converted(fee_cash_out) + Σ converted(tax_amount)   at each tx timestamp
```

- **Amount**: fee amounts follow the exact rules of the Fees page (`FIXED`, `PERCENTAGE`, `BOTH`, `MIN`; the percentage base is the parent transaction's `total_value`). Taxes contribute their `tax_amount`.
- **Pocket**: the entity's `main_currency` (for example, an IBKR account whose broker charges in JPY). A fee recorded in another currency is converted to `main_currency` at the parent transaction's timestamp with the nearest available stored rate at or before that moment. Missing rates surface through the standard missing-rate banner and `rate sync`.
- **Fallback**: an entity without `main_currency` charges fees to the fee's own recorded `(entity_id, currency)` pair without conversion.
- **Every balance view includes this term**: reconciliation walks, cash dashboards, history series, and as-of totals all see the same fee/tax cash-outs. Balance snapshots stay the reference; the fee term simply makes the computed side honest.
- **Inference applies per pocket**: if fee drains alone drive the main pocket negative on an unanchored day, the normal inferred-cash rules produce an adjustment there too (merged per day, attached to the parent spends).

### Attachment Model

Every system-generated `BALANCE_ADJUSTMENT` attaches to exactly one anchor kind:

| Anchor | Where recorded | Cardinality |
|---|---|---|
| Snapshot | `transactions.balance_snapshot_id` | 0..1 |
| Spends it funds | `balance_adjustment_links(balance_adjustment_id, linked_transaction_id)` | 1..N |

- The anchors are **mutually exclusive**: an adjustment attaches either to a snapshot or to one or more same-day spends, never both.
- A single injection may fund several spends recorded on the same day (same `entity`–cash_pocket, where cash_pocket = `COALESCE(payment_currency, currency)`): all of them are linked, and the injection's `total_value` equals the combined shortfall of the linked spends.
- Fee-driven injections on an entity's main pocket link to the parent spends even when the spends are recorded in another currency; deleting a spend removes its fees and its link in one step.
- Manual adjustments carry no attachment on either side.

### Adjustment Lifecycle

- **Edit of an attached spend**: the attached injection is recalculated against the spend's new cash impact — raised if the shortfall grows, lowered if it shrinks. If an unanchored spend becomes unfunded and no injection exists yet, one is created (mirroring record-time behavior); if the spend becomes fully funded, the injection is removed along with its links. Moving a spend to another date, entity, or currency detaches it from the old injection (which is refreshed or removed) and re-attaches/creates at the new slot; changing its type to an inflow removes the attachment entirely.
- **Edit of any other cash-impacting transaction**: the next snapshot's adjustment is refreshed (next section).
- **New spend on a day that already has an injection** (same pair): it is linked to that injection and the amount is merged into it.
- **Deleting a spend**: its link row is removed; if the adjustment's link list empties, the adjustment itself is deleted.
- **Fee or tax edit** (create, update, delete, including full-update fee replacement): the affected pairs re-reconcile — the next snapshot's adjustment per pair, plus any fee-driven injection on the main pocket.
- **Deleting a snapshot**: its attached adjustment is deleted together with it (section below).

### Automatic Recalculation

When any **cash-impacting** transaction is created, updated, or deleted for an `entity`–`cash_pocket` pair, the system recomputes the next snapshot's adjustment (Section 2.1 with the snapshot's own adjustment excluded), keeping its target balance intact; transaction-attached injections follow the *Adjustment Lifecycle* rules above:

```text
adjustment = snapshot.amount − computed_balance(snapshot.timestamp)
```

The recomputed value replaces the snapshot's existing `BALANCE_ADJUSTMENT` (matched via `balance_snapshot_id`). Only the snapshot immediately following the changed transaction needs recomputation: a later snapshot's `computed` starts from the reconciled `amount` of the one before it, which is unchanged.

Notes and similar metadata edits do not move the balance and trigger no reconciliation — they are always permitted, even on transactions dated before the latest snapshot. Fee and tax edits DO move the balance (see *Fees and Taxes as Cash Movements*): they trigger reconciliation of every affected pair.

### Deleting a Snapshot

When a snapshot is deleted, its linked `BALANCE_ADJUSTMENT` (`balance_snapshot_id = S.id`) is also deleted.

### Constraints

- A snapshot cannot be created at a date where transactions already exist at or after that timestamp for the same `entity` and **cash pocket** (`COALESCE(payment_currency, currency)`). This prevents ambiguity about which transactions fall before or after the snapshot anchor.
- A snapshot cannot be created at a date where a recurring schedule starts at or before that date for the same `entity` and **cash pocket**. This prevents future scheduled transactions from conflicting with the snapshot anchor.

> Transactions are **not** required to be dated after the latest snapshot. A transaction (or a cash-impacting edit) at any point in time is reconciled by refreshing the next snapshot's adjustment, or by injecting inferred cash — the old "`timestamp` must be strictly after the latest snapshot" rule is removed.

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
- **Exception — cash-flow and income ledgers:** these convert each transaction at the exchange rate **on that transaction's date** (previous-close lookup, Section 16.4) instead of the latest rate. Period totals are the sum of those per-date converted amounts, so historical rows are comparable and are not revalued by today's FX. See UC-27 (Cash Flow).
- **Exception — realized P&L and invested historic (Performance page):** these follow the fiscal-rule conversion in Section 16, not the latest-rate rule in this section.

---

## 10. Cost Basis

Cost basis is required by Sections 11, 12, and 13. The system uses the **FIFO (First In, First Out)** method: when units are sold, the cost of the earliest purchased units is consumed first.

FIFO runs **per entity** within each portfolio asset. A portfolio asset maps to one `market_code` and may hold buys at more than one entity (broker). Each entity keeps its own lot queue. A sell consumes lots from the queue of the entity named on that sell only. It never consumes lots bought at another entity. This is a hard rule.

### 10.1 FIFO Lot Queue at Date X

For each `(portfolio asset, entity)` pair, the FIFO lot queue is an ordered list of remaining purchase lots, computed by walking all `INVESTMENT_BUY` and `INVESTMENT_SELL` transactions of that pair with `timestamp <= date X` in chronological order:

1. Start with an empty `lot_queue` (ordered list of `{ quantity, unit_cost, buy_date }` pairs) per `(portfolio asset, entity)`.
2. For each `INVESTMENT_BUY` transaction:
   1. Append `{ quantity: transaction.quantity, unit_cost: transaction.total_value / transaction.quantity, buy_date: transaction.timestamp }` to the end of that entity's `lot_queue`.
3. For each `INVESTMENT_SELL` transaction:
   1. Set `remaining_to_consume = transaction.quantity`.
   2. While `remaining_to_consume > 0`, consume from the front of the **same entity's** `lot_queue`:
      1. If `lot_queue.front.quantity <= remaining_to_consume`: remove the front lot entirely and subtract its quantity from `remaining_to_consume`.
      2. Otherwise: reduce `lot_queue.front.quantity` by `remaining_to_consume` and set `remaining_to_consume = 0`.

The resulting per-entity `lot_queue` represents the remaining open lots of that entity at `date X`.

> `buy_date` is retained per lot solely so rule-based display conversion (Section 16) can convert each consumed lot's cost at the rate of its own purchase date. It does not affect native cost basis (Section 10.2).

### 10.2 Cost Basis of a Position at Date X

The cost basis of a portfolio asset is the sum of its entities' remaining lot costs.

```text
cost_basis = Σ over each entity of Σ (lot.quantity × lot.unit_cost) for all lots in that entity's lot_queue
```text

- `lot_queue`: the per-`(portfolio asset, entity)` queue defined in Section 10.1 at `date X`.

---

## 11. Realized Gains/Losses

Realized gain/loss is the profit or loss locked in by `INVESTMENT_SELL` transactions, relative to the FIFO cost of the specific lots consumed by each sale (Section 10.1).

> The FIFO walk (Sections 10.1/11.1) processes **all** buy/sell transactions regardless of `portfolio_assets.is_active`: sells of deactivated ("closed") assets keep contributing to historical P&L. Only current-state views (holdings, valuation, allocation) exclude inactive assets.

### 11.1 Per Sale Transaction

For each `INVESTMENT_SELL` transaction at timestamp `T`, the realized gain is computed by consuming lots from the **selling entity's** FIFO queue as it stood just before `T`:

1. Compute the selling entity's `lot_queue` (Section 10.1) using all transactions of that `(portfolio asset, entity)` with `timestamp < T`.
2. Set `remaining_to_consume = transaction.quantity`, `cost_of_sold_units = 0`.
3. Consume from the front of the selling entity's `lot_queue` until `remaining_to_consume = 0`:
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

> `total_pnl` aggregates across all entities of the asset: unrealized gain uses the asset-level cost basis (Section 10.2), and realized gain sums the per-entity FIFO sales (Section 11.2).

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
```

- `total_dividends_received`: same as Section 14.1.
- `total_invested_in_asset`: sum of `total_value` for all `INVESTMENT_BUY` transactions for this asset with `timestamp <= date X`.

### 14.3 Portfolio Dividend Yield (on Invested Historic)

Portfolio-level yield used by the performance page (all-time, display currency):

```text
dividend_yield_pct = total_dividends / invested_historic × 100    [or 0 if invested_historic = 0]
```

- `total_dividends`: Σ of `total_value` over all `INCOME` transactions with `income_category = 'dividends'`, each converted to the display currency at its own payment-date rate (fallbacks reported per Section 16.4, scope `dividends`).
- `invested_historic`: as defined in Section 16.3.

The sibling metric `total_interest` sums `income_category = 'interest'` payments with the identical conversion rule (scope `interest`) but is displayed separately and never feeds Total Return or the yields above: interest is earned on cash balances, not on investment decisions.

### 14.4 Per-Asset Yields in Display Currency

Sections 14.1/14.2 are defined natively per asset; when shown in a converted view, numerator and denominator convert under the same rate so the percentage is preserved.

---

## 15. Currency Exposure Summary

The currency exposure summary aggregates the portfolio's value broken down by currency, without conversion. It answers: how much of the portfolio is denominated in each currency?

### 15.1 Cash Exposure per Currency

For each cash pocket present in any `entity`–`cash_pocket` pair:

```text
cash_exposure[cash_pocket] = sum of cash_balance (Section 2.1) across all entities for this cash pocket at date X
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

*Implemented (Phases 1–2 of `doc/plans/fiscal_rules_pnl_engine.md`): true FIFO lots, the `PnlRule` registry, proceeds-currency handling, buy-date invested-historic conversion, rate-fallback flags, and rule assignment over time via `fiscal_periods` with a `transactions.fiscal_rule` snapshot. The rule applied to a sell is its frozen snapshot, or the profile's `default_fiscal_rule` when no period covered the sell date; if the profile default is also unset, the read path infers from the locale (fallback `default`).*

### 16.1 Native P&L (rule-independent)

Every rule consumes the same **native** realized gain per sell (Section 11.1), computed from true FIFO lots:

```text
native_gain = sell_total − cost_basis
```

- `sell_total`: `transaction.total_value` of the `INVESTMENT_SELL`, in the asset's `currency`.
- `cost_basis`: sum of the consumed lots' cost (Section 10.1/11.1), in the asset's `currency`.

Native P&L never depends on the rule — rules only define the display-currency conversion. The realized-gains table therefore always shows native values.

### 16.2 Rule Set

The rule applied to a sell is the one active on its **sell date** (resolved via `fiscal_periods`, UC-47) and frozen onto the transaction at creation (`transactions.fiscal_rule`). With no period covering the sell date, the snapshot falls back to the profile's `default_fiscal_rule`. When the profile default is also unset, the snapshot is NULL and the read path infers from the locale (`es → spain`, `ja → japan`, else `default`).

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

**Cash balance note:** the cash balance (Section 2.1) also tracks in `payment_currency` when set — the sell's proceeds increase the `payment_currency` cash pocket, not the asset `currency` pocket. The `gross_amount` field (= `total_value × fx_rate`) is the cash-impacting amount.

### 16.3 Invested Historic (buy-side conversion)

`total_invested_historic` is about invested cash only — it is rule-independent and always buy-date converted:

```text
total_invested_historic = Σ over INVESTMENT_BUY transactions of
    buy_total × rate(buy.currency → display, buy.timestamp)
```

### 16.4 Rate Lookup and Fallback

- Historical rates come from the `currencies` table (Section 9), looked up as of the required date.
- **Previous-close convention**: lookups resolve strictly **on or before** the requested date — never forward (no lookahead bias). A Sunday lookup takes Friday's close.
- Non-trading days (weekends, market holidays) have no stored FX rows by design, so a previous-close resolution is the normal case, not an anomaly. A resolution is only reported as a fallback when it is **stale: at least two business days old** (`business_days_between(rate_date, reference_date) >= 2`; Saturdays and Sundays do not count toward the gap; there is no holiday calendar). Example: Friday's close silently serves Saturday, Sunday and Monday lookups; on Tuesday it surfaces as `closest-in-time`.
- If no rate exists at all for a currency, the value is included unconverted (as in Section 9) and flagged.

The same staleness rule drives the "Exchange rates from …" banners on the cash-flow and income pages: `RateMetadata.stale` is computed against the server's current date, so a banner appears only when the latest stored close is genuinely outdated (e.g. the daily rate sync has been failing for two or more business days), never for yesterday's fresh close.

---

## 17. Taxable P&L and Tax Computation (Tax Page)

Phase 3 implemented the taxable P&L view (§17.1–§17.5). Phase 4 extends with tax computation, confirmed-vs-computed resolution, user-editable rates, and per-item drill-down (§17.6–§17.13). See `doc/plans/tax_page.md`.

### 17.1 Ruleset extension

A ruleset now bundles the realized-gains conversion (Section 16.2), a **fiscal-year start** `(month, day)`, and **dividend** treatment. v1 uses the natural year `(1, 1)` for all rulesets; the field is configurable. Dividends are taxable income, not sells, and convert at their `payment_date` (fallback `timestamp`) rate — independent of the sell-conversion rules.

### 17.2 Realized gains

Per sell, the taxable amount is the rule-converted value (Section 16.2) under the sell's frozen `fiscal_rule`, then reduced by any linked exemption (Section 17.4). Losses pass through unchanged. Sells come from the per-entity FIFO walk (Section 11.1): each sell consumes only the lots of its own entity.

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
| `transaction_id` | int | FK to `transactions`. |
| `market_code` / `ticker` / `name` | string or null | Asset identifiers. |
| `category` | `"capital_gains"` or `"dividends"` | Transaction type. |
| `date` | date | Sell date or dividend payment date. |
| `native_amount` | float | Gross amount in the item's native currency (sale: `sell_total − cost_basis`; dividend: `total_value`). |
| `display_amount` | float | Plain FX conversion of `native_amount` at the transaction date (§16.4) — rule-independent and pre-exemption. |
| `taxable_amount` | float | Rule-converted (§16.2) then exemption-reduced (§17.4) taxable base in display currency. |
| `tax_owed` | float or null | Computed tax from brackets (null if no rates). |
| `fiscal_rule` | string or null | The rule applied to this row: the sell's frozen `fiscal_rule` (fallback resolved ruleset) or, for dividends, the rule active on the payment date (`fiscal_periods`, fallback resolved ruleset). |
| `tax_policy` | string or null | Linked exemption's `exemption_type` (fallback `description`), e.g. `NISA`; null when no exemption is linked. |
| `currency` | string | Native currency of the item. |

`display_amount` and `taxable_amount` differ only through the ruleset conversion (§16.2) and any exemption (§17.4); for the Spain rule they coincide unless an exemption applies.

Items are sorted by date within each fiscal year.

### 17.13 Profile default ruleset

`profiles.default_fiscal_rule` (nullable) participates in the **write-time snapshot** for new sells and is surfaced (read + edit) in Settings and on the Tax page header.

**Write-time snapshot** (at transaction creation):

1. `fiscal_periods` containing the sell date → period's `rule_key`.
2. `profiles.default_fiscal_rule` (if set).
3. Otherwise NULL (the read path infers from locale).

**Read-time effective ruleset** (when computing P&L):
The profile default does **not** override the `ruleset` request parameter. The effective ruleset resolves via `rule_for_locale` (`es → spain`, `ja → japan`, else `default`). Per-item `fiscal_rule = sale.fiscal_rule or resolved_ruleset`, so existing snapshots are never overwritten. The extended response echoes the profile default as `default_ruleset` for display; it does not participate in the computation.

---

## Appendix: Calculations Not Currently Defined

The following calculations are common in financial portfolio applications and are not yet specified in this document. They may warrant future definition:

- **Time-weighted return (TWR)** — return metric that neutralizes the effect of cash flows; standard for fund performance comparison.
- **Money-weighted return (IRR)** — return metric that accounts for the timing and size of cash flows; reflects investor experience.
