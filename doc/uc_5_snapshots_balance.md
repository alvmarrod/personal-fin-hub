# Tier 5 — Snapshots & Balance

Balance snapshots anchor the cash balance of an `(entity, currency)` pair to a known value at a point in time. All subsequent cash computations build on top of this anchor.

---

## UC-18: Create Balance Snapshot

**Trigger**: User records a known cash balance for a specific entity and currency at a point in time

**Modeling decision**:
- Creates a `balance_snapshots` row: entity_id, currency, amount, timestamp
- The snapshot anchors the cash balance. All transactions with `timestamp > snapshot.timestamp` are accumulated on top of this base
- One snapshot per `(entity, currency)` pair is active at a time (newer supersedes older in computation, but older rows are retained for audit)

**IF first snapshot for this (entity, currency) pair**:
- No existing snapshots for this pair
- INSERT snapshot. No adjustment transaction needed
- The snapshot becomes the base: `cash_balance = snapshot.amount + Σ(post-snapshot transactions)`

**IF subsequent snapshot for same (entity, currency) pair**:
- At least one prior snapshot exists for this pair
- INSERT snapshot
- Compute: `expected_balance = snapshot of prior amount + Σ(transactions between prior snapshot and new snapshot timestamp)`
- Compute: `adjustment_amount = new_snapshot.amount - expected_balance`
- Auto-create a `BALANCE_ADJUSTMENT` transaction:
  - `type = BALANCE_ADJUSTMENT`
  - `entity_id` = same as snapshot
  - `currency` = same as snapshot
  - `timestamp` = new_snapshot.timestamp - 1 day
  - `total_value` = adjustment_amount (positive if snapshot is higher than expected, negative if lower)
  - `notes` = reference to the snapshot

**Rejected alternatives**:
- Adjustment as a separate table → rejected: `BALANCE_ADJUSTMENT` is semantically a transaction (it adjusts cash). Using the transactions table keeps all cash-impact events in one place. Analytics filter it out explicitly
- No adjustment, just override → rejected: would lose the reconciliation history. The adjustment transaction provides an audit trail of what was corrected
- Single snapshot per entity (not per currency) → rejected: accounts hold multiple currencies independently. A JPY balance and a USD balance at the same entity are separate

**Entities affected**: `balance_snapshots` (write), `transactions` (write, if subsequent snapshot), `entities` / `currencies` (read for FK validation)

**UI pages**: Balance Snapshots page (`/balance-snapshots`)

**Constraints**:
- `entity_id` must exist (not soft-deleted)
- `currency` must exist in `currencies`
- `amount` ≥ 0
- Pre-check: no transaction for `(entity_id, currency)` with `timestamp ≥ snapshot.timestamp` (409 if violated)
- Pre-check: no schedule for `(entity_id, currency)` with `start_date ≤ snapshot.timestamp` (409 if violated)
- The BALANCE_ADJUSTMENT transaction is excluded from cash flow analytics (filtered by type)

---

## UC-19: Delete Balance Snapshot

**Trigger**: User removes a balance snapshot

**Modeling decision**:
- Hard DELETE from `balance_snapshots` table
- If the snapshot had an associated `BALANCE_ADJUSTMENT` transaction, that transaction is also deleted
- After deletion, cash balance computation falls back to the next most recent snapshot (or from the beginning if no other snapshots exist)

**Rejected alternatives**:
- Soft delete → rejected: snapshots are anchoring points, not historical data. A deleted snapshot should not affect any computation
- Keeping the adjustment transaction → rejected: without the snapshot, the adjustment has no basis. It would create an unexplained cash jump

**Entities affected**: `balance_snapshots` (write), `transactions` (write, delete adjustment if exists)

**UI pages**: Balance Snapshots page (`/balance-snapshots`)

**Constraints**:
- Snapshot must exist
- Associated BALANCE_ADJUSTMENT transaction is auto-deleted

---

## UC-20: View Cash Balance

**Trigger**: Any view that needs to display cash balance (Dashboard, Entities, Currencies, Analytics)

**Modeling decision**:
- Cash balance is computed, not stored. It's the result of: snapshot base + accumulated transactions
- Two computation paths depending on snapshot state

**IF no snapshot exists for (entity, currency)**:
- `cash_balance = Σ (all transactions for this entity/currency, applying cash impact rules)`
- Cash impact: +MONEY_IN, +INTEREST, +DIVIDEND, +INVESTMENT_SELL, -MONEY_OUT, -INVESTMENT_BUY
- BALANCE_ADJUSTMENT is excluded from the sum

**IF snapshot exists with timestamp < date X (Path A)**:
- `base = snapshot.amount`
- `delta = Σ (transactions for this entity/currency with timestamp > snapshot.timestamp AND ≤ date X, applying cash impact)`
- `cash_balance = base + delta`

**IF snapshot exists with timestamp = date X (Path B)**:
- `base = snapshot.amount`
- `delta = Σ (transactions for this entity/currency ON date X, applying cash impact)`
- `cash_balance = base + delta`

**Currency model for aggregation**:
- Per-entity, per-currency balances are computed independently
- To get total cash across all entities and currencies: sum all per-pair balances
- To display in a target currency: convert each pair's balance using the `currencies` table rate for that date, then sum
- Conversion uses market rate from `currencies` table (not transaction fx_rate)

**Rejected alternatives**:
- Storing running balance on each transaction → rejected: snapshots and transaction edits would require recalculating all subsequent rows. Computed balances are always correct
- Single balance per entity → rejected: multi-currency accounts need per-currency breakdowns

**Entities affected**: `transactions` (read), `balance_snapshots` (read), `currencies` (read for conversion)

**UI pages**: All views that display cash (Dashboard, Entities, Currencies, Cash Flow, Income, Transactions)

**Constraints**:
- BALANCE_ADJUSTMENT transactions are excluded from cash flow sums
- Future transactions (`timestamp > now()`) are excluded from current balance (included only in historical views)
- Snapshot-aware computation ensures accuracy even with incomplete transaction history
