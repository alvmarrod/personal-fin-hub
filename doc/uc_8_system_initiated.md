# Tier 8 — System-Initiated

Operations triggered by the system (APScheduler, startup events) rather than direct user actions. These create real financial records.

---

## UC-38: Scheduler Fires Schedule

**Trigger**: APScheduler job fires at the cron/date trigger time

**Modeling decision**:
- Reads the schedule's embedded fields and creates a fresh `transactions` row
- `timestamp` = `datetime.now()` (the fire time, not the schedule's start_date)
- All other fields are copied from the schedule's embedded data

**Sequence**:
1. `SELECT * FROM schedules WHERE id = ?`
2. IF `end_date` is set AND today > `end_date`: call `remove_schedule(id)`, return None (auto-expire)
3. Construct `TransactionCreate` from embedded fields: `type`, `entity_id`, `currency`, `total_value`, `notes`
4. IF schedule has `portfolio_asset_id`, `quantity`, `unit_price`, `transaction_category`: copy those too
5. INSERT into `transactions`
6. COMMIT

**Currency model**:
- `currency` is copied from the schedule
- `payment_currency` and `fx_rate` are NOT set by the scheduler — they default to NULL
- If the schedule represents a cross-currency operation (e.g., monthly USD buy from JPY account), the user should update the materialized transaction after it fires to add `payment_currency` and `fx_rate`
- This is a deliberate design choice: FX rates change, and locking them at schedule creation time would be unrealistic

**Rejected alternatives**:
- Pre-computing all future transactions → rejected: would pollute `transactions` with future entries. Transactions should represent realized events only
- Storing fx_rate on the schedule → rejected: rate would be stale after first period. Better to set at fire time
- Skipping the commit on failure → rejected: failed fires are logged but don't affect the schedule's future execution

**Entities affected**: `schedules` (read), `transactions` (write)

**Constraints**:
- Atomic: single INSERT with rollback on failure
- Failed fires are logged but don't block the scheduler
- The schedule remains active after firing (continues to fire next period)

---

## UC-39: Auto-Create Balance Adjustment

**Trigger**: A new balance snapshot is created for an `(entity, currency)` pair that already has a prior snapshot

**Modeling decision**:
- When a subsequent snapshot is created (UC-18), the system computes the expected balance between the prior snapshot and the new one
- If the actual snapshot amount differs from expected, a `BALANCE_ADJUSTMENT` transaction is auto-created
- `timestamp` = new_snapshot.timestamp - 1 day (placed on the day before the snapshot to avoid interference)

**Sequence** (as part of UC-18):
1. Find the most recent prior snapshot for this `(entity, currency)` pair
2. Compute expected balance: `prior_snapshot.amount + Σ(transactions between prior and new snapshot)`
3. `adjustment_amount = new_snapshot.amount - expected_balance`
4. INSERT `BALANCE_ADJUSTMENT` transaction with `total_value = adjustment_amount`

**IF transaction is later edited/deleted between snapshots**:
- The BALANCE_ADJUSTMENT is recomputed to maintain the snapshot's target balance
- This automatic recalculation ensures consistency regardless of transaction changes

**Currency model**:
- Adjustment is in the same `currency` as the snapshot
- The adjustment preserves the snapshot's target balance regardless of intervening transaction edits

**Rejected alternatives**:
- Manual adjustment entry → rejected: error-prone. The system can compute the exact delta automatically
- Updating the prior snapshot → rejected: snapshots are anchor points. Changing a prior snapshot would invalidate all subsequent computations
- No adjustment, just override → rejected: loses the reconciliation audit trail

**Entities affected**: `transactions` (write), `balance_snapshots` (read)

**Constraints**:
- BALANCE_ADJUSTMENT is excluded from all cash flow analytics
- Recomputed automatically when transactions between snapshots are modified

---

## UC-40: Scheduler Startup Re-Registration

**Trigger**: Application startup (main.py startup event)

**Modeling decision**:
- On boot, loads all schedules from the database and registers APScheduler jobs
- Ensures all recurring operations resume after a restart

**Sequence**:
1. `SELECT * FROM schedules ORDER BY id`
2. For each schedule: register an APS job with the appropriate trigger (cron or date)
3. If any jobs registered: start the scheduler

**Currency model**:
- No currency-specific logic — this is purely job registration
- The schedule's embedded `currency` field is used when the job fires (UC-35)

**Rejected alternatives**:
- Persisting APScheduler state → rejected: APScheduler's in-memory state is lost on restart. Re-registering from DB is simpler and more reliable
- Not re-registering → rejected: schedules would silently stop firing after a restart

**Entities affected**: `schedules` (read), APScheduler (job registration)

**Constraints**:
- Jobs are registered in schedule ID order (deterministic)
- If a schedule's periodicity is CUSTOM and `custom_cron` is NULL, the job is skipped
