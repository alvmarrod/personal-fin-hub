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
3. Compute `occurrence_date` from the scheduled fire date
4. Check `SELECT 1 FROM schedule_occurrences WHERE schedule_id = ? AND occurrence_date = ?` — if exists, skip (already materialized)
5. Construct `TransactionCreate` from embedded fields: `type`, `entity_id`, `currency`, `total_value`, `notes`
6. INSERT into `transactions`
7. INSERT into `schedule_occurrences (schedule_id, occurrence_date, transaction_id)`
8. COMMIT

**Currency model**:

- `currency` is copied from the schedule
- `payment_currency` and `fx_rate` are NOT set by the scheduler — they default to NULL
- If the schedule represents a cross-currency operation (e.g., monthly USD buy from JPY account), the user should update the materialized transaction after it fires to add `payment_currency` and `fx_rate`
- This is a deliberate design choice: FX rates change, and locking them at schedule creation time would be unrealistic

**Rejected alternatives**:

- Pre-computing all future transactions → rejected: would pollute `transactions` with future entries. Transactions should represent realized events only
- Storing fx_rate on the schedule → rejected: rate would be stale after first period. Better to set at fire time
- Tag-based deduplication via `notes LIKE '%[schedule:N]%'` → rejected: manual edits to the transaction's notes or timestamp break the check, causing duplicate materializations
- Skipping the commit on failure → rejected: failed fires are logged but don't affect the schedule's future execution

**Entities affected**: `schedules` (read), `transactions` (write), `schedule_occurrences` (read/write)

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

---

## UC-41: Catch Up Missed Fires

**Trigger**: Application startup (main.py lifespan), before UC-40

**Modeling decision**:

- Persists `last_shutdown_at` timestamp in a new `scheduler_state` table on every shutdown
- On startup, computes all intended fire dates between `last_shutdown_at` and now
- Creates backdated transactions for each missed fire (timestamp = fire date at midnight)
- Idempotent: checks `schedule_occurrences` for `(schedule_id, occurrence_date)` before creating. A row in that table means the occurrence was already materialized — regardless of what happened to the transaction later (date edits, amount changes, note rewrites)
- No time limit on backfill — all missed fires are caught up regardless of duration
- Calls `_recalculate_adjustments()` for each catch-up transaction to maintain balance snapshot consistency
- CUSTOM periodicity catch-up is skipped (would require croniter dependency)

**Sequence**:

1. On shutdown: `INSERT INTO scheduler_state (key, value) VALUES ('last_shutdown_at', now)`
2. On startup:
   a. Read `last_shutdown_at` from `scheduler_state`
   b. If no previous timestamp: bootstrap from earliest schedule's `start_date` (first deploy)
   c. If no previous timestamp and no schedules: skip
   d. For each schedule: compute fire dates in `[window_start, now]` (respects `end_date`)
    e. For each fire date: check `schedule_occurrences` for idempotency, create backdated tx, INSERT into `schedule_occurrences`, trigger adjustment recalc
   f. Commit all changes

**Fire date computation by periodicity**:

- ONE_OFF: single date if it falls in window
- DAILY: iterate +1 day from start_date
- WEEKLY: iterate +7 days from start_date
- MONTHLY: advance to next month's start_date day (clamped to month end)
- QUARTERLY: advance +3 months
- ANNUALLY: advance +1 year
- CUSTOM: skipped (no cron parsing without croniter)

**Currency model**:

- Same as UC-38: `currency` copied from schedule, `payment_currency` and `fx_rate` default to NULL

**Rejected alternatives**:

- Using APScheduler's built-in catch-up → rejected: APScheduler does not persist state between restarts
- Storing all future transactions upfront → rejected: violates "transactions represent realized events"
- Adding croniter dependency → rejected: unnecessary dependency for a single use case

**Entities affected**: `scheduler_state` (read/write), `transactions` (read/write), `schedule_occurrences` (read/write), `balance_snapshots` (read)

**Constraints**:

- Runs synchronously before `init_scheduler()` (UC-40)
- Idempotent: safe to run multiple times without duplicating transactions — the `schedule_occurrences` UNIQUE constraint enforces this at the DB level
- Failed catch-ups are logged but don't block scheduler startup
- `_recalculate_adjustments` failures are caught per-transaction to prevent one failure from blocking others

---

## UC-46: Scheduled Price Sync

**Trigger**: APScheduler cron job at `sync_cron_hours` UTC (default `[0, 12]` — 00:00 and 12:00)

**Modeling decision**:

- Runs a **full** refresh of auto-tracked portfolio assets' prices (`POST /market/sync-prices` semantics with `full=true`), paced 5s between symbols.
- Fixed UTC hours (not per-exchange calendars) deliberately replace any exchange→timezone/close-time mapping: 00:00 catches the Americas/Europe closes (~21:00 / ~16:30 UTC), 12:00 catches the Asia closes (~06:00 UTC). Max staleness ~12h, acceptable for closing prices.
- Registered once in `init_scheduler()` (UC-40) as a fixed cron job (not per-schedule), with `max_instances=1` + coalesce so it never overlaps a manual or auto sync.

**Sequence**:

1. Fire at a `sync_cron_hours` UTC hour.
2. Enumerate active `portfolio_assets` where `tracking_mode != 'manual'`.
3. For each symbol, paced `sync_cron_pace_seconds` apart: `GET /symbol/{code}`, upsert price + history into `prices`.
4. Update `market_assets.last_synced_at` on success only.
5. Skip silently if another sync is already running (single-flight) or the circuit is open.

**Currency model**:

- Prices are stored in each asset's native currency (unchanged); no FX conversion at sync time.

**Rejected alternatives**:

- Per-exchange timezone + close-time + holiday calendar → rejected: DST and exchange schedule changes make this unmaintainable; a fixed two-a-day UTC cadence covers the major market close windows without it.
- One refresh/day → rejected: misses either Asia (00:00) or Americas/Europe (12:00); two runs cover both.

**Entities affected**: `market_assets` (read `market_code`/`tracking_mode`, write `last_synced_at`), `prices` (write), `portfolio_assets` (read)

**Constraints**:

- Single-flight: never runs concurrently with a manual/auto sync.
- Full refresh ignores the freshness window (guarantees a complete daily dataset).
- Failures are logged; the circuit breaker fail-fasts a confirmed outage.
