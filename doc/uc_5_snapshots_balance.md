# Tier 5 — Snapshots & Balance

Balance snapshots anchor the cash balance of an `(entity, currency)` pair to a known value at a point in time. A snapshot's `amount` is the **target** balance at its `timestamp`; the system reconciles the gap between the target and what the recorded transactions imply using a signed `BALANCE_ADJUSTMENT` transaction.

---

## Reconciliation Model

This section is the shared reference for UC-18, UC-19, UC-20, UC-39, and the transaction use cases.

**Three quantities** for a snapshot `S` at `timestamp = ts`, `amount = target`:

| Quantity | Definition |
|---|---|
| `computed_balance(ts)` | `base(ts)` + Σ transactions in `[base(ts).timestamp, ts)`, **excluding `S`'s own `BALANCE_ADJUSTMENT`** (`balance_snapshot_id = S.id`). |
| `target_balance` | `S.amount` — the user-stated ground truth. |
| `actual_balance(ts)` | `computed + S's adjustment` — must equal `target`. This is what every read path shows. |

**Reconciliation rule:**

```text
adjustment = target − computed_balance(ts)
```

- The adjustment is a single signed `BALANCE_ADJUSTMENT` transaction placed at `ts − 1 day at 23:59:59` — the last event before the snapshot — so `actual_balance` lands exactly on `target`.
- `computed_balance` excludes **only** the snapshot's own adjustment (via `balance_snapshot_id`), never other adjustments in the interval; excluding more would be circular or wrong once standalone (injected) adjustments coexist.

**Every snapshot has its own adjustment** — including the first one for a pair. For the first snapshot there is no prior snapshot, so `base = 0` and `computed = Σ` all transactions from the origin; the same rule applies.

**Injection (inferred cash).** A spend (`INVESTMENT_BUY`, `MONEY_OUT`, `TRANSFER_OUT`) that would otherwise be unexplained can be paired with an injected `BALANCE_ADJUSTMENT` immediately before it (`balance_snapshot_id = NULL`). The choice is offered for every spend:

- **debit** the balance (default when a prior snapshot or recorded balance establishes the funds) — no injection;
- **inject** inferred cash (default when no prior reference and the spend would drive the pair negative).

Inflows (`INCOME`, `INVESTMENT_SELL`, `TRANSFER_IN`) always add to the balance; there is no injection concept. Deviating from the default is allowed and surfaced with a confirmation warning.

**Cash-handling persistence.** The chosen handling is stored on the spend as `balance_mode` (`'inject'` | `'debit'`; `NULL` = smart default decided at record time). Every transaction therefore carries a durable record of how its cash impact was reconciled; later reconciliation passes honor this record instead of re-deriving it.

**Attachment model.** Every system-generated `BALANCE_ADJUSTMENT` attaches to exactly one anchor kind:

| Anchor | Where recorded | Cardinality |
|---|---|---|
| Snapshot | `transactions.balance_snapshot_id` | 0..1 |
| Spends it funds | `balance_adjustment_links(balance_adjustment_id, linked_transaction_id)` | 1..N |

- Anchors are mutually exclusive: a snapshot attachment **or** same-day spend attachments — never both.
- One injection can fund several spends recorded on the same day (same pair): all are linked and the amount equals their combined shortfall.
- Manual adjustments carry no attachment on either side.

**Adjustment lifecycle**: editing an attached spend recalculates its injection (raise/lower; create if newly unfunded; remove+unlink if fully funded; date/entity/currency moves detach and re-attach, type change to inflow detaches); a new same-day spend merges into the existing injection and gets linked; deleting a spend removes its link — when no link remains, the adjustment itself is deleted; deleting a snapshot deletes its attached adjustment (UC-19 below).

---

## UC-18: Create Balance Snapshot

**Trigger**: User records a known cash balance for a specific entity and currency at a point in time

**Modeling decision**:

- Creates a `balance_snapshots` row: entity_id, currency, amount, timestamp
- The snapshot anchors the cash balance: all transactions with `timestamp > snapshot.timestamp` accumulate on top of it (Section 2.1 of `calculations.md`)
- The system always reconciles the snapshot with its own `BALANCE_ADJUSTMENT` (see Reconciliation Model above) — including the **first** snapshot for the pair

**Sequence**:

1. Validate FK references (entity, currency)
2. INSERT snapshot
3. Compute `computed_balance(ts)` excluding this snapshot's own adjustment
4. Compute `adjustment = amount − computed_balance(ts)`
5. INSERT/UPDATE a `BALANCE_ADJUSTMENT` transaction at `ts − 1 day 23:59:59` with `total_value = adjustment`, linked via `balance_snapshot_id = S.id`

**Rejected alternatives**:

- No adjustment for the first snapshot → rejected: the first snapshot is an anchor like any other; without its own adjustment a backdated transaction before it could not be reconciled without silently changing the anchor
- Adjustment as a separate table → rejected: `BALANCE_ADJUSTMENT` is semantically a transaction (it adjusts cash). Using the transactions table keeps all cash-impact events in one place
- No adjustment, just override → rejected: loses the reconciliation history. The adjustment transaction provides an audit trail of what was corrected
- Single snapshot per entity (not per currency) → rejected: accounts hold multiple currencies independently

**Entities affected**: `balance_snapshots` (write), `transactions` (write, the adjustment)

**UI pages**: Balance Snapshots page (`/balance-snapshots`)

**Constraints**:

- `entity_id` must exist (not soft-deleted)
- `currency` must exist in `currencies`
- `amount` ≥ 0
- Pre-check: no transaction for `(entity_id, currency)` with `timestamp ≥ snapshot.timestamp` (409 if violated)
- Pre-check: no schedule for `(entity_id, currency)` with `start_date ≤ snapshot.timestamp` (409 if violated)
- The BALANCE_ADJUSTMENT transaction is excluded from income/expense analytics (it is not income or expense) but is included in the cash balance (Section 1 of `calculations.md`)

---

## UC-19: Delete Balance Snapshot

**Trigger**: User removes a balance snapshot

**Modeling decision**:

- Hard DELETE from `balance_snapshots`
- Its linked `BALANCE_ADJUSTMENT` (matched via `balance_snapshot_id = S.id`) is also deleted
- After deletion, cash balance computation falls back to the next most recent snapshot (or from the origin if none)

**Rejected alternatives**:

- Soft delete → rejected: snapshots are anchoring points, not historical data
- Keeping the adjustment → rejected: without its snapshot the adjustment has no basis and would create an unexplained cash jump

**Entities affected**: `balance_snapshots` (write), `transactions` (write, delete the adjustment)

**UI pages**: Balance Snapshots page (`/balance-snapshots`)

**Constraints**:

- Snapshot must exist
- Its linked BALANCE_ADJUSTMENT is auto-deleted

---

## UC-20: View Cash Balance

**Trigger**: Any view that needs to display cash balance (Dashboard, Entities, Currencies, Analytics)

**Modeling decision**:

- Cash balance is computed, not stored
- `actual_balance(X) = base(X) + Σ(transactions with base(X).timestamp ≤ t < X)` (Section 2.1 of `calculations.md`)
- `base(X)` = latest snapshot strictly before `X` (its `amount`), or `0` if none
- `BALANCE_ADJUSTMENT` applies its signed `total_value` (it is a real cash movement)

**Currency model for aggregation**:

- Per-entity, per-currency balances are computed independently
- To total across currencies: convert each pair's balance using the `currencies` table rate, then sum

**Rejected alternatives**:

- Storing running balance on each transaction → rejected: edits would require recalculating all subsequent rows
- Single balance per entity → rejected: multi-currency accounts need per-currency breakdown

**Entities affected**: `transactions` (read), `balance_snapshots` (read), `currencies` (read for conversion)

**UI pages**: All views that display cash (Dashboard, Entities, Currencies, Cash Flow, Income, Transactions)

**Constraints**:

- `BALANCE_ADJUSTMENT` is excluded from income/expense sums but included in cash balance
- Future transactions (`timestamp > now()`) are excluded from current balance (included only in historical views)
