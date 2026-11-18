# Tier 5 — Snapshots & Balance

Balance snapshots anchor the cash balance of an `(entity, cash_pocket)` pair to a known value at a point in time. A cash pocket is identified by `COALESCE(payment_currency, currency)` — the currency in which the cash actually lands. A snapshot's `amount` is the **target** balance at its `timestamp`; the system reconciles the gap between the target and what the recorded transactions imply using a signed `BALANCE_ADJUSTMENT` transaction.

> **Timezone note**: Snapshot timestamps are user-meaningful time. The frontend shows the picker as the profile-timezone wall clock, labels it with the zone (`Time in Europe/Madrid · GMT+1`), and sends the matching UTC instant for storage. The adjustment is placed one second before the snapshot (`ts − 1s`, UTC). `now()` in UC-20 is the current UTC instant. All `timestamp` comparisons (UC-20 future-exclusion) are strict UTC. See `doc/timezone_model.md`.

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

- The adjustment is a single signed `BALANCE_ADJUSTMENT` transaction placed at `ts − 1 second` (UTC) — the last event strictly inside the snapshot's own interval — so `actual_balance` lands exactly on `target`, regardless of the calendar day and of any earlier snapshot taken the same day.
- `computed_balance` excludes **only** the snapshot's own adjustment (via `balance_snapshot_id`), never other adjustments in the interval; excluding more would be circular or wrong once standalone (injected) adjustments coexist.

**Every snapshot has its own adjustment** — including the first one for a pair. For the first snapshot there is no prior snapshot, so `base = 0` and `computed = Σ` all transactions from the origin; the same rule applies.

**Cash funding.** A spend is funded from its cash pocket first. `INVESTMENT_BUY` adds three further options (it never drives the pocket negative):

| `cash_handling` | Funding order | Shortfall |
|---|---|---|
| `debit` | pocket only | reject the buy (422) |
| `debit_pocket_main` | pocket, then main-currency conversion | reject the buy (422) |
| `inject` | pocket, then inferred cash | inject the remainder |
| `inject_pocket_main` | pocket, then main-currency conversion, then inferred cash | inject whatever is left |
| `NULL` | treated as `inject_pocket_main` | inject whatever is left |

`MONEY_OUT` / `TRANSFER_OUT` keep the two-way choice: **debit** the known balance (no injection, may go negative) or **inject** inferred cash into the pocket.

The conversion is a generated FX pair (`TRANSFER_OUT` main + `TRANSFER_IN` pocket) at the buy instant, linked via `transaction_funding_links`. Inflows (`INCOME`, `INVESTMENT_SELL`, `TRANSFER_IN`) always add to the balance; there is no injection concept.

**Cash-handling persistence.** The chosen handling is stored on the spend as `cash_handling` (`'inject'`, `'debit'`, `'debit_pocket_main'`, `'inject_pocket_main'`; `NULL` = default decided at record time). Every transaction therefore carries a durable record of how its cash impact was reconciled; later reconciliation passes honor this record instead of re-deriving it.

**Attachment model.** Every system-generated `BALANCE_ADJUSTMENT` attaches to exactly one anchor kind:

| Anchor | Where recorded | Cardinality |
|---|---|---|
| Snapshot | `transactions.balance_snapshot_id` | 0..1 |
| Spends it funds | `balance_adjustment_links(balance_adjustment_id, linked_transaction_id)` | 1..N |

- Anchors are mutually exclusive: a snapshot attachment **or** same-day spend attachments — never both.
- One injection can fund several spends recorded on the same day (same cash pocket — `COALESCE(payment_currency, currency)`): all are linked and the amount equals their combined shortfall.
- Manual adjustments carry no attachment on either side.

**Adjustment lifecycle**: editing an attached spend recalculates its injection (raise/lower; create if newly unfunded; remove+unlink if fully funded; date/entity/currency moves detach and re-attach, type change to inflow detaches); a new same-day spend merges into the existing injection and gets linked; deleting a spend removes its link — when no link remains, the adjustment itself is deleted; deleting a snapshot deletes its attached adjustment (UC-19 below).

---

## UC-18: Create Balance Snapshot

**Trigger**: User records a known cash balance for a specific entity and cash pocket at a point in time

**Modeling decision**:

- Creates a `balance_snapshots` row: entity_id, currency, amount, timestamp
- The snapshot anchors the cash balance of the `COALESCE(payment_currency, currency)` cash pocket: all transactions whose cash pocket matches accumulate on top of it (Section 2.1 of `calculations/finance.md`)
- The system always reconciles the snapshot with its own `BALANCE_ADJUSTMENT` (see Reconciliation Model above) — including the **first** snapshot for the pair

**Sequence**:

1. Validate FK references (entity, currency) and reject a future timestamp (`> now + 60s`)
2. If a snapshot already exists at the same instant for the pair, UPDATE its amount/notes instead of inserting a second anchor
3. INSERT snapshot (when the instant is free)
4. Compute `computed_balance(ts)` excluding this snapshot's own adjustment
5. Compute `adjustment = amount − computed_balance(ts)`
6. INSERT/UPDATE a `BALANCE_ADJUSTMENT` transaction at `ts − 1s` with `total_value = adjustment`, linked via `balance_snapshot_id = S.id`
7. Recompute the adjustment of the **next** snapshot for the pair, if any: inserting or replacing an anchor changes its interval base

**Backdated snapshots are allowed.** A snapshot may be dated before existing transactions; it is ground truth at its instant and the reconciliation model above handles it. Nothing is rejected because transactions exist after it.

**Rejected alternatives**:

- Rejecting a snapshot when transactions exist after it (the old 409 pre-check) → rejected: the snapshot is the source of truth, and the reconciliation model already absorbs the difference
- No adjustment for the first snapshot → rejected: the first snapshot is an anchor like any other; without its own adjustment a backdated transaction before it could not be reconciled without silently changing the anchor
- Adjustment as a separate table → rejected: `BALANCE_ADJUSTMENT` is semantically a transaction (it adjusts cash). Using the transactions table keeps all cash-impact events in one place
- No adjustment, just override → rejected: loses the reconciliation history. The adjustment transaction provides an audit trail of what was corrected
- Single snapshot per entity (not per currency) → rejected: accounts hold multiple currencies independently

**Entities affected**: `balance_snapshots` (write), `transactions` (write, the adjustment)

**UI pages**: Balances page (`/balance-snapshots`)

**Constraints**:

- `entity_id` must exist (not soft-deleted)
- `currency` must exist in `currencies`
- `amount` ≥ 0
- `timestamp` must not be in the future (`> now + 60s` → 422)
- A snapshot at an instant that already has one for the pair replaces it (the UI warns before saving)
- The BALANCE_ADJUSTMENT transaction is excluded from income/expense analytics (it is not income or expense) but is included in the cash balance (Section 1 of `calculations/finance.md`)

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

**UI pages**: Balances page (`/balance-snapshots`)

**Constraints**:

- Snapshot must exist
- Its linked BALANCE_ADJUSTMENT is auto-deleted

---

## UC-20: View Cash Balance

**Trigger**: Any view that needs to display cash balance (Dashboard, Entities, Currencies, Analytics)

**Modeling decision**:

- Cash balance is computed, not stored
- `actual_balance(X) = base(X) + Σ(transactions with base(X).timestamp ≤ t < X)` (Section 2.1 of `calculations/finance.md`)
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
- Future transactions (`timestamp > now()` where `now()` = current UTC instant) are excluded from current balance (included only in historical views)
