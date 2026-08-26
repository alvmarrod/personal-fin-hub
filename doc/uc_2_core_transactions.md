# Tier 2 — Core Transactions

Single-operation transactions. Each creates one row in `transactions`. The currency model is introduced here and applies to all subsequent tiers.

---

## Currency Model for Transactions

Every transaction has:

- **`currency`** (required): The denomination of the transaction. For investments, this is the asset's native currency. For money in/out, this is the currency the user records the transaction in.
- **`payment_currency`** (optional): What actually left or entered the user's account. If NULL, same as `currency` (no conversion).
- **`fx_rate`** (optional): The broker-applied conversion rate: 1 unit of `currency` = `fx_rate` units of `payment_currency`. If NULL and `payment_currency` is set, the system auto-fills from the `currencies` table (market rate as of transaction date). User can override with the actual broker rate.
- **`gross_amount`** (optional): Total before fees/tax, in `payment_currency`.
- **`net_amount`** (optional): Total after fees/tax, in `payment_currency`.

**Same-currency transaction** (most common): `payment_currency` is NULL, `fx_rate` is NULL. The transaction is entirely in one currency.

**Cross-currency transaction**: `payment_currency` differs from `currency`. `fx_rate` captures the conversion. `gross_amount` and `net_amount` are in `payment_currency`.

---

## UC-06: Record Income

**Trigger**: User records a cash deposit, salary, or other income received

**Modeling decision**:

- Creates a single `INCOME` transaction with an `income_category` ∈ {salary, other, dividends, interest, cashback}
- Increases cash balance for the entity
- Counted as income source in analytics (Income by Source, Cash Flow)
- The category is a strict subclassification of income: salary/other are bare income, dividends carry the dividend metadata fields (see UC-10), interest is bare income classified as `interest`, cashback is bare income classified as `cashback` (debit card cashback and similar rewards)

**IF same currency (simple case)**:

- `currency` = the currency received (e.g., JPY)
- `payment_currency` = NULL (no conversion)
- `fx_rate` = NULL
- `total_value` = amount received

**IF cross-currency (foreign income)**:

- `currency` = the foreign currency received (e.g., EUR)
- `payment_currency` = the user's account currency (e.g., JPY)
- `fx_rate` = auto-filled from `currencies` table (EUR→JPY market rate as of transaction date), user can override with actual rate
- `total_value` = amount in `currency` (EUR)
- `gross_amount`, `net_amount` = amounts in `payment_currency` (JPY), if user provides them

**Rejected alternatives**:

- Using a separate transaction type per income kind (dividend, interest, etc.) → rejected: all income is `INCOME`; `income_category` carries the semantics. A single income type keeps analytics, validation, and UI uniform while the category selects the applicable fields and data placement
- Separating the FX conversion into its own transaction → rejected: the deposit and conversion are a single atomic event. Two transactions would double-count cash flow

**Entities affected**: `transactions` (write)

**UI pages**: Add Income modal (from Dashboard header), Transactions page (`/transactions`), Income page (`/income`)

**Constraints**:

- `entity_id` must exist (not soft-deleted)
- `currency` must exist in `currencies`
- `total_value` > 0
- `income_category` must be one of salary, other, dividends, interest, cashback
- If `payment_currency` is set, must exist in `currencies` and differ from `currency`
- Balance reconciliation: an `INCOME` is a balance *increase*, so it never requires an injection. Recording it at any date is allowed; if a later `balance_snapshot` exists, its `BALANCE_ADJUSTMENT` is refreshed so the snapshot's target balance is maintained (see Tier 5 Reconciliation Model).
- `investment_transaction_category` (optional): NORMAL (default), DCA (dollar-cost averaging), or REBALANCE (portfolio rebalancing). Only valid for `type = INVESTMENT_BUY/INVESTMENT_SELL`. Display-only; does not affect cash balance calculation.

---

## UC-07: Record Money Out

**Trigger**: User records a cash withdrawal, expense, or other money leaving an account

**Modeling decision**:

- Creates a single `MONEY_OUT` transaction
- Decreases cash balance for the entity
- Counted as outflow in Cash Flow analytics

**IF same currency (simple case)**:

- `currency` = the currency withdrawn (e.g., JPY)
- `payment_currency` = NULL
- `fx_rate` = NULL
- `total_value` = amount withdrawn

**IF cross-currency (foreign withdrawal)**:

- `currency` = the foreign currency (e.g., USD)
- `payment_currency` = the user's account currency (e.g., JPY)
- `fx_rate` = auto-filled from `currencies` table, user can override
- `total_value` = amount in `currency` (USD)

**Rejected alternatives**:

- Modeling expenses differently from money out → rejected: both are cash decreases. The `type` field distinguishes them semantically, but the data model is identical
- Negative `total_value` for outflows → rejected: `total_value` is always positive. The `type` field determines the sign in calculations (MONEY_OUT subtracts)

**Entities affected**: `transactions` (write)

**UI pages**: Transactions page (`/transactions`)

**Constraints**: Same as UC-06, except for balance reconciliation: `MONEY_OUT` is a balance *decrease*, so the inject/debit choice (Tier 5 Reconciliation Model) is offered instead — inject inferred cash before the outflow, or debit the balance (letting it go negative if that reflects reality). The chosen handling is persisted as `cash_handling` on the transaction and returned by the API; when an injection is created it is attached to this spend via `balance_adjustment_links` (see Attachment Model in `calculations.md` §8).

---

## UC-08: Record Investment Buy

**Trigger**: User records a purchase of an investment asset (stock, ETF, ETC, fund)

**Modeling decision**:

- Creates a single `INVESTMENT_BUY` transaction
- Decreases cash balance (the user spent money)
- Increases position (quantity held) for the portfolio asset
- `currency` = the asset's native currency (from `market_assets.currency_code`). This is what the asset is priced in
- `quantity` and `unit_price` are in `currency`
- `total_value` = `quantity × unit_price` (in `currency`)

**Inferred cash (first buy for entity+currency)**:
If this is the first `INVESTMENT_BUY` for this `(entity_id, currency)` pair and no balance snapshots or `INCOME`/`BALANCE_ADJUSTMENT` transactions exist for this pair, the default is to **inject** inferred cash:

- Create a `BALANCE_ADJUSTMENT` transaction at `timestamp - 1 day 23:59:59` with `total_value = total_value` of the buy (the cash that must have existed before the purchase), `balance_snapshot_id = NULL`.
- This records the pre-existing cash so the buy does not drive the pair negative. The user may instead choose to debit the balance (no injection), letting it go negative if that reflects reality (see Tier 5 Reconciliation Model). The chosen handling is persisted (`cash_handling`) and any created injection is attached to the buy via `balance_adjustment_links`.

**IF same currency (asset currency = account currency)**:

- `currency` = asset's native currency (e.g., USD)
- `payment_currency` = NULL (same as currency)
- `fx_rate` = NULL
- Example: Buy AAPL with USD in a USD account

**IF cross-currency (asset currency ≠ account currency)**:

- `currency` = asset's native currency (e.g., USD)
- `payment_currency` = account currency (e.g., JPY)
- `fx_rate` = auto-resolved from `currencies` table on creation (`get_rate(currency, payment_currency)`). User can override with broker's actual rate. If cleared on edit, re-resolves automatically.
- `gross_amount` = auto-computed from `total_value × fx_rate` on creation/update. User can override.
- `net_amount` = auto-computed from `gross_amount` (minus fees where known). User can override.
- Example: Buy CSPX.L (USD-denominated ETF) through a JPY account. User pays JPY, asset is priced in USD

**Rejected alternatives**:

- Recording the buy in the account currency only → rejected: loses the asset's native price. P&L calculations need the original currency cost basis
- Creating two transactions (FX conversion + buy) → rejected: the buy and conversion are a single atomic event from the user's perspective
- Storing fx_rate on the portfolio_asset → rejected: the rate varies per transaction. Different buys of the same asset may happen at different rates

**Entities affected**: `transactions` (write)

**UI pages**: Add Asset modal (from Dashboard header), Transactions page (`/transactions`)

**Constraints**:

- `entity_id` must exist
- `currency` must exist (typically matches `market_assets.currency_code` for the linked asset)
- `portfolio_asset_id` must exist if provided
- `quantity` > 0, `unit_price` > 0
- If `payment_currency` set: must exist, must differ from `currency`
- Balance reconciliation applies: a buy is a balance *decrease*, so the inject/debit choice (Tier 5 Reconciliation Model) is offered and persisted (`cash_handling`); an injection is attached via `balance_adjustment_links`; a later snapshot's adjustment is refreshed to maintain its target balance.

---

## UC-09: Record Investment Sell

**Trigger**: User records a sale of an investment asset

**Modeling decision**:

- Creates a single `INVESTMENT_SELL` transaction
- Increases cash balance (the user received money)
- Decreases position (quantity held) for the portfolio asset
- `currency` = the asset's native currency
- Triggers FIFO lot consumption for realized P&L calculation

**IF same currency**:

- `currency` = asset's native currency (e.g., USD)
- `payment_currency` = NULL
- `fx_rate` = NULL

**IF cross-currency**:

- `currency` = asset's native currency (e.g., USD)
- `payment_currency` = account currency (e.g., JPY)
- `fx_rate` = auto-filled, user can override
- `gross_amount`, `net_amount` = in `payment_currency`

**Rejected alternatives**:

- Recording proceeds in account currency only → rejected: FIFO needs the original currency cost basis to compute realized gains accurately
- Linking sell to specific buy transactions → rejected: FIFO is computed algorithmically from chronological order, not explicit links. This avoids O(n²) relationship management

> **Proceeds currency note:** `payment_currency` on the sell records where the proceeds are received. Empty = proceeds stay in the asset `currency`; set (with `fx_rate`) = proceeds are received/converted to that currency at sell time. The cash balance (§2.1) also tracks in `payment_currency` when set — the sell's proceeds increase the `payment_currency` cash pocket, not the asset `currency` pocket. The planned fiscal-rules P&L engine (`calculations.md` §16, UC-47) uses this to convert proceeds to the display currency.

**Entities affected**: `transactions` (write)

**UI pages**: Transactions page (`/transactions`)

**Constraints**:

- `quantity` ≤ current net quantity held (cannot sell more than owned)
- Same FK constraints as UC-08. A sell is a balance *increase* (proceeds received), so it needs no injection; a later snapshot's adjustment is refreshed as usual (Tier 5 Reconciliation Model).

---

## UC-10: Record Dividend

**Trigger**: User records a dividend payment received from an investment

**Modeling decision**:

- Creates a single `INCOME` transaction with `income_category = 'dividends'`
- Increases cash balance
- Has dedicated dividend fields because dividends have unique attributes (record date, payment date, dividend type, withholding tax)
- Uses a **two-currency model**: `dividend_currency` (what the fund paid) and `dividend_payment_currency` (what landed in the account). These may differ when the fund pays in one currency and the broker converts

**Currency fields**:

- `currency` = the denomination for cash impact calculations. Typically matches `dividend_payment_currency`
- `dividend_currency` = what the fund/company paid in (e.g., USD for a US stock dividend)
- `dividend_payment_currency` = what the user received in their account (e.g., JPY if the broker converted)
- `dividend_fx_rate` = conversion rate from `dividend_currency` → `dividend_payment_currency` (if different)
- `payment_currency` = same as `dividend_payment_currency` (redundant but consistent with other transaction types)

**IF dividend paid in same currency as account**:

- `dividend_currency` = USD
- `dividend_payment_currency` = USD
- `dividend_fx_rate` = NULL
- `currency` = USD
- `payment_currency` = NULL

**IF dividend paid in foreign currency, broker converts**:

- `dividend_currency` = USD (fund paid in USD)
- `dividend_payment_currency` = JPY (broker converted to JPY)
- `dividend_fx_rate` = rate applied by broker (e.g., 150.5)
- `currency` = JPY (what cash the user received)
- `payment_currency` = NULL (no second conversion — the dividend IS the payment)

**IF dividend received in foreign currency, held as-is**:

- `dividend_currency` = USD
- `dividend_payment_currency` = USD (user chose to hold in USD)
- `dividend_fx_rate` = NULL
- `currency` = USD
- `payment_currency` = JPY (if the user's account is JPY, this records the conversion for cash tracking)

**Rejected alternatives**:

- Using a bare `INCOME` without the `dividends` category → rejected: loses dividend-specific metadata (record_date, payment_date, dividend_type, withholding tax structure). Analytics need to distinguish dividends from other income
- Modeling withholding tax as a separate transaction → rejected: the tax is semantically part of the dividend event. `transaction_taxes` rows with `tax_type=WITHHOLDING` linked to the dividend transaction is the correct model
- Single `fx_rate` field instead of `dividend_fx_rate` → rejected: dividends have a different FX path than regular transactions. The fund pays in one currency, the broker may convert at a different rate than the spot market

**Entities affected**: `transactions` (write), `transaction_taxes` (write, if withholding tax)

**UI pages**: Dividends page (`/dividends`), Income page (`/income`), Transactions page (`/transactions`)

**Constraints**:

- `portfolio_asset_id` should be provided (links dividend to the asset)
- `dividend_type` must be one of: regular, special, qualified (if provided)
- `record_date` ≤ `payment_date` (if both provided)
- Withholding taxes: `transaction_taxes` with `tax_type=WITHHOLDING`, `currency` = `dividend_currency` (tax is in the original dividend currency)
- Balance reconciliation: a dividend is a balance *increase*, so it needs no injection; a later snapshot's adjustment is refreshed as usual (Tier 5 Reconciliation Model).
