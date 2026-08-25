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

## UC-39: Reconcile Balance (Auto-Create Balance Adjustment)

**Trigger**:

1. A balance snapshot is created (UC-18) — reconcile its target against the ledger.
2. A cash-impacting transaction is created/updated/deleted — refresh the next snapshot's adjustment.
3. A spend is recorded with no prior reference that funds it — inject inferred cash.

**Modeling decision**:

- A `BALANCE_ADJUSTMENT` is a real signed cash transaction: positive adds cash, negative removes it. It is included in the cash balance (`calculations.md` Section 1) but excluded from income/expense analytics.
- Reconciliation: `adjustment = snapshot.amount − computed_balance(snapshot.timestamp)`, where `computed_balance` excludes **only** the snapshot's own adjustment (matched via `balance_snapshot_id`), so the calculation is non-circular.
- The adjustment is placed at `snapshot.date − 1 day 23:59:59` — the last moment before the snapshot — so `actual_balance` lands exactly on the target.
- Every snapshot has its own adjustment, including the **first** one for a pair (`base = 0`, sum from origin).
- Injected inferred cash is a standalone `BALANCE_ADJUSTMENT` (`balance_snapshot_id = NULL`) placed just before the spend(s) it funds and attached to them via `balance_adjustment_links`.

**Sequence** (snapshot creation, UC-18):

1. Find the prior snapshot for the pair (if any) — else `base = 0`.
2. Compute `computed = base + Σ(transactions in the interval, excluding this snapshot's own adjustment)`.
3. `adjustment = snapshot.amount − computed`.
4. UPSERT a `BALANCE_ADJUSTMENT` at `snapshot.date − 1 day 23:59:59` with `total_value = adjustment`, `balance_snapshot_id = snapshot.id`.

**IF a cash-impacting transaction is later edited/deleted**:

- Find the next snapshot after the changed transaction; recompute its `computed` (excluding its own adjustment) and refresh its adjustment. A later snapshot's `computed` starts from the reconciled `amount` of the one before it, so only the immediately-following snapshot needs updating.

**Currency model**:

- The adjustment is in the same `currency` as the snapshot (or, for injection, as the spend).

**Rejected alternatives**:

- Manual adjustment entry → rejected: the system computes the exact delta automatically.
- Updating the prior snapshot → rejected: snapshots are anchor points; changing one would invalidate all downstream computation.
- No adjustment, just override → rejected: loses the reconciliation audit trail.
- Excluding all `BALANCE_ADJUSTMENT` from the balance math → rejected: an adjustment is a real cash movement and must be counted; only the snapshot's *own* adjustment is excluded from its own reconciliation to avoid circularity.

**Entities affected**: `transactions` (write), `balance_snapshots` (read/write)

**Constraints**:

- `BALANCE_ADJUSTMENT` is excluded from income/expense analytics but included in cash balance.
- Recomputed automatically when cash-impacting transactions change; balance-neutral edits (fees, taxes, notes) trigger no reconciliation.

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

---

## UC-47: Scheduled Rate Sync

**Trigger**: APScheduler cron job `rate_sync` at `rate_sync_hour_utc` UTC (default 01:00; set to `null` in config to disable)

**Modeling decision**:

- Runs the same deep FX sync as the Currencies-page button (`sync_rates()`), paced 5s between window requests.
- Fires **once daily at 01:00 UTC**: after the global FX market close (~21:00–22:00 UTC / 5pm ET), so the previous day's closing rate for every pair is captured. Fixed UTC deliberately mirrors UC-46's rationale — no per-user locale, no DST fragility.
- Deep backfill range = earliest transaction date − 7 days → today, chunked into ≤1-year windows per the Market API's max span; without transactions it uses the provider's default recent window.
- Registered once in `init_scheduler()` as a fixed cron job with `max_instances=1`, coalesce, and a 6h misfire grace so an offline server catches up on boot.

**Sequence**:

1. Fire at `rate_sync_hour_utc` UTC.
2. Enumerate distinct currency codes → all unique pairs (`{CODE}{BASE}=X`).
3. For each pair, fetch history per ≤1y window; upsert each day's `Close` into `currencies`.
4. Skip silently if the circuit is open.

**Currency model**:

- Rates are stored per pair direction in the `currencies` table (native units); conversion/inversion happens at read time (UC-34 analytics).

**Rejected alternatives**:

- Per-user-locale scheduling time → rejected: freshness depends on display preferences and DST; FX close is a global event anchored to UTC.
- Piggybacking price sync (UC-46) → rejected: couples two concerns and makes it impossible to disable or retime one independently.
- Manual-only sync → rejected: rolling provider windows silently starve historical conversions (the exact gap that motivated this use case).

**Entities affected**: `currencies` (write), `transactions` (read earliest timestamp)

**Constraints**:

- Max 1 year of history per Market API request — windows never exceed 365 days.
- Circuit-open skip is identical to price sync.
