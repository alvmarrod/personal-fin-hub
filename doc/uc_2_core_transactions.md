# Tier 2 — Core Transactions

Single-operation transactions. Each creates one row in `transactions`. The currency model is introduced here and applies to all subsequent tiers.

> **Timezone note**: Transaction timestamps are user-meaningful time. The frontend interprets them in the profile timezone and sends them as UTC instants for storage. The injection at `timestamp − 1 day 23:59:59` is computed in the profile timezone before UTC conversion. See `doc/timezone_model.md`.

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

**Constraints**: Same as UC-06, except for balance reconciliation: `MONEY_OUT` is a balance *decrease*, so the inject/debit choice (Tier 5 Reconciliation Model) is offered instead — inject inferred cash before the outflow, or debit the balance (letting it go negative if that reflects reality). The chosen handling is persisted as `cash_handling` on the transaction and returned by the API; when an injection is created it is attached to this spend via `balance_adjustment_links` (see Attachment Model in `calculations/finance.md` §8).

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

- Create a `BALANCE_ADJUSTMENT` transaction at `timestamp − 1 day at 23:59:59` in the profile timezone (then converted to UTC for storage), `balance_snapshot_id = NULL`. The injection targets the spend's **cash pocket** (`COALESCE(payment_currency, currency)`):
  - Same-currency buy (`payment_currency` is NULL): inject into the `currency` pocket with `total_value = total_value` of the buy.
  - Cross-currency buy (`payment_currency` is set): inject into the `payment_currency` pocket with `total_value = gross_amount` (the JPY/USD equivalent, i.e. `total_value × fx_rate`). This records the cash that must have existed in the account currency to fund the purchase.
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

**Entity-driven default for `payment_currency`** (applied when creating a new buy, before the user overrides anything):

- `entities.supports_multi_currency = TRUE` → `payment_currency` defaults to `NULL` (assumes the buy is funded entirely from the existing asset-currency pocket). Known simplification: a real multi-currency broker may partially fund the buy via a fresh conversion when the existing balance is insufficient — not modeled; see `doc/plans/multi_currency_buy_funding.md` (accepted limitation, relies on the Tier 5 Reconciliation Model to absorb the resulting drift).
- `entities.supports_multi_currency = FALSE` → `payment_currency` defaults to `entities.main_currency`, `fx_rate` auto-resolved as in the cross-currency case above.
- `entities.supports_multi_currency = NULL` (unclassified) → no default applied; today's fully manual behavior (user picks "IF same currency" or "IF cross-currency" explicitly).
- The user can still override `payment_currency`/`fx_rate` manually on the specific buy.

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
- If `payment_currency` not set: the entity-driven default above applies (`NULL` → the asset-currency pocket; `entities.main_currency` when `supports_multi_currency = FALSE`)
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

**Entity-driven default for `payment_currency`** (applied when creating a new sell, before the user overrides anything):

- `entities.supports_multi_currency = TRUE` → `payment_currency` defaults to `NULL` (proceeds stay in the asset's native currency — matches reality exactly; a single sale converts nothing by itself).
- `entities.supports_multi_currency = FALSE` → `payment_currency` defaults to `entities.main_currency`, `fx_rate` auto-resolved as in the cross-currency case above.
- `entities.supports_multi_currency = NULL` (unclassified) → no default applied; fully manual behavior, user picks the "same currency" or "cross-currency" case explicitly.
- The user can still override `payment_currency`/`fx_rate` manually on the specific sell.

**Rejected alternatives**:

- Recording proceeds in account currency only → rejected: FIFO needs the original currency cost basis to compute realized gains accurately
- Linking sell to specific buy transactions → rejected: FIFO is computed algorithmically from chronological order, not explicit links. This avoids O(n²) relationship management

> **Proceeds currency note:** `payment_currency` on the sell records where the proceeds are received. Empty = proceeds stay in the asset `currency`; set (with `fx_rate`) = proceeds are received/converted to that currency at sell time. The cash balance (§2.1) also tracks in `payment_currency` when set — the sell's proceeds increase the `payment_currency` cash pocket, not the asset `currency` pocket. The planned fiscal-rules P&L engine (`calculations/finance.md` §16, UC-47) uses this to convert proceeds to the display currency.

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
- Uses the SAME currency model as `INVESTMENT_SELL` (UC-09): `currency` = the dividend's declared currency, always fixed (analogous to a sell's `currency` = the asset's native currency); `payment_currency`/`fx_rate` are the optional broker-conversion layer, used only when the broker actually converts the payout to another currency. There is no dividend-specific currency field
- `total_value` = the gross dividend amount declared, in `currency`, BEFORE withholding tax (same convention as `INVESTMENT_BUY`'s `total_value`: bruto, before fees/tax). Withholding tax is a separate deduction recorded via `transaction_taxes` (see Constraints) and does not change `total_value`; the net amount received is `total_value` minus the withholding tax row(s), derivable rather than stored

**IF dividend paid in same currency as account**:

- `currency` = USD (the dividend's declared currency)
- `payment_currency` = NULL
- `fx_rate` = NULL

**IF broker converts to another currency**:

- `currency` = USD (the dividend's declared currency — unchanged, always fixed)
- `payment_currency` = JPY (the broker converted the payout to this currency)
- `fx_rate` = rate applied by the broker (auto-resolved on creation, user can override — same behavior as UC-09's cross-currency case)

**Entity-driven default for `payment_currency`** (applied when creating a new dividend, before the user overrides anything):

- `entities.supports_multi_currency = TRUE` → `payment_currency` defaults to `NULL` (dividend stays in its declared currency — matches reality exactly; a dividend payout is a single inflow, not a split payment).
- `entities.supports_multi_currency = FALSE` → `payment_currency` defaults to `entities.main_currency`, `fx_rate` auto-filled.
- `entities.supports_multi_currency = NULL` (unclassified) → no default applied; fully manual behavior, user picks the "same currency" or "broker converts" case explicitly.
- The user can still override `payment_currency`/`fx_rate` manually on the specific dividend.

**Rejected alternatives**:

- Using a bare `INCOME` without the `dividends` category → rejected: loses dividend-specific metadata (record_date, payment_date, dividend_type, withholding tax structure). Analytics need to distinguish dividends from other income
- Modeling withholding tax as a separate transaction → rejected: the tax is semantically part of the dividend event. `transaction_taxes` rows with `tax_type=withholding` linked to the dividend transaction is the correct model
- A dividend-specific two-currency model (`dividend_currency`/`dividend_payment_currency`/`dividend_fx_rate`, separate from the generic `currency`/`payment_currency`/`fx_rate`) → rejected: a dividend doesn't need a different FX path from a sell. Both are a single inflow that either stays in its native currency or gets converted once by the broker at the event date — exactly what `payment_currency`/`fx_rate` already express for `INVESTMENT_SELL`. The dividend-specific fields only duplicated this without adding expressiveness, while creating an asymmetry with UC-09 that caused real inconsistencies (see `doc/plans/dividend_withholding.md`)

**Entities affected**: `transactions` (write), `transaction_taxes` (write, if withholding tax)

**UI pages**: Dividends page (`/dividends`), Income page (`/income`), Transactions page (`/transactions`)

**Constraints**:

- `portfolio_asset_id` should be provided (links dividend to the asset)
- `dividend_type` must be one of: regular, special, qualified (if provided)
- `record_date` ≤ `payment_date` (if both provided)
- Withholding taxes: `transaction_taxes` with `tax_type=withholding`, `currency` = `currency` (the tax is levied by the source country before any broker conversion, i.e. in the dividend's declared currency — the same value as the transaction's own `currency` field; no special case needed)
- Balance reconciliation: a dividend is a balance *increase*, so it needs no injection; a later snapshot's adjustment is refreshed as usual (Tier 5 Reconciliation Model).
