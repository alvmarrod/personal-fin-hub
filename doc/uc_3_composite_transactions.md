# Tier 3 — Composite Transactions

Operations that create multiple rows atomically. All rows succeed or all roll back.

---

## UC-11: Record Full Transaction

**Trigger**: User records a transaction with associated fees and/or taxes in a single operation

**Modeling decision**:

- Creates: 1 `transactions` row + N `transaction_fees` rows + M `transaction_taxes` rows
- Atomic: if any fee or tax INSERT fails, ALL changes roll back
- This is the canonical pattern for recording any transaction that has costs attached

**Currency model**:

- The transaction follows the same currency rules as UC-06 through UC-10 (depending on `type`)
- **Fee currency**: each fee row has its own `currency` field. The fee currency must match either the transaction's `currency` OR the transaction's `payment_currency` (if set). This covers:
  - Broker commission in account currency (e.g., JPY fee on a USD buy → fee currency = JPY = payment_currency)
  - Platform fee in asset currency (e.g., USD fee on a USD buy → fee currency = USD = currency)
  - FX conversion fee in either currency
- **Tax currency**: each tax row has its own `currency` field. Same constraint: must match `currency` or `payment_currency`
- `gross_amount` = total before fees/tax, in `payment_currency`
- `net_amount` = total after fees/tax, in `payment_currency`

**Sequence**:

1. Validate all FK references (`_resolve_fks`)
2. INSERT transaction
3. For each fee: INSERT `transaction_fees` with `transaction_id` = new tx.id
4. For each tax: INSERT `transaction_taxes` with `transaction_id` = new tx.id
5. COMMIT

**Rejected alternatives**:

- Fees as separate transactions → rejected: breaks the atomic unit of "action + cost". P&L calculations would need to reconstruct the relationship
- Fees as fields on the transaction row → rejected: a transaction can have multiple fees of different types. Normalization into a child table is cleaner
- Allowing fee currency to be any currency → rejected: a fee must be in a currency that's relevant to the transaction. An arbitrary fee currency would create orphaned cash flows

**Entities affected**: `transactions` (write), `transaction_fees` (write), `transaction_taxes` (write)

**UI pages**: Add Asset modal, Add Income modal, Add Transaction modal, Edit Transaction modal

**Constraints**:

- All transaction constraints from UC-06 through UC-10 apply
- Fee currency ∈ {transaction.currency, transaction.payment_currency}
- Tax currency ∈ {transaction.currency, transaction.payment_currency}
- `gross_amount` ≥ `net_amount` (fees + taxes reduce the total)

**Fee/tax cash impact**: fees and taxes live in `transaction_fees` / `transaction_taxes` and are real cash-outs charged to `entities.main_currency` (converted from their recorded currency when they differ; NULL main currency = own recorded pair, no conversion). They change the cash balance that snapshots anchor. Adding, editing, or removing a fee or tax therefore participates in the Tier 5 reconciliation model: the affected pairs' snapshot adjustments and any fee-driven injections on the main pocket are recalculated. See *Fees and Taxes as Cash Movements* in `calculations.md` §8.

---

## UC-12: Transfer Between Entities

**Trigger**: User transfers funds between two entities (e.g., bank to broker, broker to broker)

**Modeling decision**:

- Creates two mirror transactions: `TRANSFER_OUT` from source entity + `TRANSFER_IN` to destination entity
- The `TRANSFER_IN`/`TRANSFER_OUT` types are **cash-flow neutral**: they are excluded from income and expense sums (Cash Flow, Income by Source). The type carries the direction, so each leg still affects its entity's cash balance (OUT subtracts, IN adds)
- The two transactions are logically paired by same timestamp, same amount, opposite directions
- They are NOT FK-linked — they are independent records that happen to be created atomically

**Currency model**:

- **Same-currency transfer**: Both legs use the same currency. `amount` is in that currency. No FX.
  - Out leg: `type=TRANSFER_OUT`, `entity_id=from_entity`, `currency=EUR`, `total_value=amount` (type determines direction)
  - In leg: `type=TRANSFER_IN`, `entity_id=to_entity`, `currency=EUR`, `total_value=amount` (type determines direction)
- **Cross-currency transfer**: Source and destination accounts are in different currencies.
  - Out leg: `type=TRANSFER_OUT`, `entity_id=from_entity`, `currency=EUR`, `total_value=amount`, `payment_currency=JPY`, `fx_rate=market_rate`
  - In leg: `type=TRANSFER_IN`, `entity_id=to_entity`, `currency=JPY`, `total_value=amount`
  - The FX conversion happens implicitly between the two legs
- **Optional fees**: Fees are attached only to the outgoing leg (they're the cost of sending). Fees follow UC-11 currency constraints.

**Rejected alternatives**:

- `MONEY_OUT` + `INCOME` legs → rejected: these types are semantically income/expense. Cash Flow and Income by Source analytics classify them as outflows/inflows, so a transfer appeared as an expense for the sender and income for the receiver. Direction must be encoded in transfer-specific types (`TRANSFER_OUT`/`TRANSFER_IN`) that analytics can exclude from income/expense sums while still applying to cash balance
- Single `TRANSFER` type with from/to fields → rejected: would require schema changes to transactions (from/to columns). Two mirror transactions reuse the existing column layout with direction in the type
- A single `TRANSFER` type for both legs (no direction) → rejected: cash balance and UI cannot distinguish which leg is the source without extra fields
- FK-linking the two transactions → rejected: transactions are independent records. Linking would add complexity without benefit — the pairing is implicit (same timestamp, same amount, opposite directions)
- Creating a separate `transfers` table → rejected: transfers ARE transactions. A separate table would duplicate the cash flow model and complicate analytics

**Entities affected**: `transactions` (write × 2), `transaction_fees` (write, optional)

**UI pages**: Transfers page (`/transfers`)

**Constraints**:

- `from_entity_id` ≠ `to_entity_id`
- Both entities must exist (not soft-deleted)
- `amount` > 0
- `currency` must exist
- Balance reconciliation applies per leg: `TRANSFER_OUT` is a balance *decrease* (inject/debit choice, persisted as `cash_handling` on the out-leg), `TRANSFER_IN` is a balance *increase* (no injection); an out-leg injection is attached via `balance_adjustment_links`, and each leg's later snapshot adjustment is refreshed (Tier 5 Reconciliation Model)
- Leg types: outgoing leg MUST be `TRANSFER_OUT`, incoming leg MUST be `TRANSFER_IN`
- Atomic: if either INSERT fails, ALL roll back

---

## UC-13: Batch Import Transactions

**Trigger**: User imports multiple transactions at once (bulk load)

**Modeling decision**:

- Creates N transactions atomically via `POST /transactions/batch`
- Each transaction in the batch follows the same rules as UC-06 through UC-10 (depending on `type`)
- All succeed or all roll back — no partial imports

**Currency model**:

- Each transaction in the batch has its own currency fields
- Transactions in the batch can be in different currencies
- Cross-currency rules from UC-06-10 apply per-transaction

**Rejected alternatives**:

- Non-atomic batch → rejected: partial imports leave the database in an inconsistent state. User would need to figure out which transactions were imported
- CSV-specific endpoint → rejected: the batch endpoint is generic. CSV parsing is a frontend concern. The backend just receives a list of transactions

**Entities affected**: `transactions` (write × N)

**UI pages**: Transactions page (`/transactions`) — import functionality

**Constraints**:

- At least one transaction in the batch
- Each transaction must pass all individual transaction constraints
- Atomic: all succeed or all roll back
