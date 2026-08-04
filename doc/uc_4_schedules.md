# Tier 4 — Schedules

Recurring or one-off future operations. Schedules are self-contained — they embed the fields needed to create transactions when they fire.

---

## UC-14: Create Recurring Schedule

**Trigger**: User sets up a recurring operation (monthly salary, quarterly DCA, annual fee, etc.)

**Modeling decision**:

- Creates a `schedules` row with embedded transaction data
- NO template transaction is created in `transactions` — the schedule IS the source of truth
- When the scheduler fires, it reads the embedded fields and creates a fresh transaction row
- This eliminates double-counting: `transactions` contains only realized (fired) rows

**Embedded fields on schedule**:

- `description` — human-readable label
- `start_date`, `end_date` — active period
- `periodicity_type` — ONE_OFF, DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY, CUSTOM
- `custom_cron` — for CUSTOM periodicity
- `entity_id` — which entity this applies to
- `currency` — the transaction currency (required)
- `total_value` — the amount per occurrence
- `type` — the transaction type (MONEY_IN, MONEY_OUT, INVESTMENT_BUY, etc.)
- `notes` — optional annotation
- `portfolio_asset_id` — for INVESTMENT_BUY/SELL schedules, which asset to trade. Combined with `total_value`, the backend auto-computes quantity from the market price at fire time via `_resolve_investment_fields`

**Currency model**:

- `currency` on the schedule is the transaction currency. When the scheduler fires, it creates a transaction with this currency
- The schedule does NOT store `payment_currency` or `fx_rate` — these are re-evaluated at fire time (see UC-35)
- For cross-currency recurring operations (e.g., monthly USD ETF buy from JPY account): the schedule stores `currency=USD`, and when it fires, the user can provide/update the `fx_rate` and `payment_currency` on the materialized transaction
- For same-currency recurring operations (e.g., monthly JPY salary): `currency=JPY`, no FX needed

**Rejected alternatives**:

- FK to a template transaction → rejected: would create a row in `transactions` that's not a real transaction. Queries would need to filter out templates. Embedded fields avoid this entirely
- Storing fx_rate on the schedule → rejected: FX rates change. A monthly buy at a locked rate for 12 months would be unrealistic. Rate should be evaluated at fire time
- Storing payment_currency on the schedule → rejected: same reason. The user's payment situation may change (e.g., account currency changes)

**Entities affected**: `schedules` (write), APScheduler (job registration)

**UI pages**: Income page (`/income`) — Add Income modal (recurring mode), Schedules page (`/schedules`)

**Constraints**:

- `entity_id` must exist
- `currency` must exist
- `start_date` must be valid
- If `balance_snapshot` exists for `(entity_id, currency)`: `start_date` must be > snapshot.timestamp
- `periodicity_type` must be valid enum
- CUSTOM requires `custom_cron` to be non-null
- ONE_OFF fires once on `start_date`

---

## UC-15: Edit Schedule

**Trigger**: User modifies an existing schedule

**Modeling decision**:

- Updates the `schedules` row
- Calls `sync_schedule()` to re-register the APScheduler job with new parameters
- Changes to `total_value`, `entity_id`, `currency`, `type`, or `notes` affect ALL future materializations
- Past materialized transactions are NOT affected — they are independent records

**Currency model**:

- Changing `currency` on the schedule changes the currency of all FUTURE materialized transactions
- Past transactions retain their original currency
- If the new `currency` differs from before, the user should verify that the entity has an account in that currency

**Rejected alternatives**:

- Updating past transactions → rejected: past transactions are realized financial events. Modifying them would alter historical accuracy
- Creating a new schedule instead of editing → rejected: loses the schedule history and APS job continuity

**Entities affected**: `schedules` (write), APScheduler (job re-registration)

**UI pages**: Income page (`/income`) — Edit Schedule modal, Schedules page (`/schedules`)

**Constraints**:

- Schedule must exist
- Same FK constraints as UC-14
- Balance snapshot constraint applies if `currency` or `entity_id` changed

---

## UC-16: Delete Schedule

**Trigger**: User removes a recurring or future one-off operation

**Modeling decision**:

- Hard DELETE from `schedules` table
- Calls `remove_schedule()` to unregister the APScheduler job
- Does NOT delete any transactions that were already materialized by the schedule — they remain as independent records in `transactions`

**Rejected alternatives**:

- Soft delete → rejected: schedules are operational config, not historical data. Once deleted, the recurring operation should not appear anywhere
- Cascading delete of materialized transactions → rejected: those are real financial events that happened. Deleting them would destroy history

**Entities affected**: `schedules` (write), APScheduler (job removal)

**UI pages**: Income page (`/income`) — Confirm Delete modal, Schedules page (`/schedules`)

**Constraints**:

- Schedule must exist
- APScheduler job is removed even if the schedule row delete fails (best-effort cleanup)

---

## UC-17: Project Future Occurrences

**Trigger**: Frontend needs to display projected income/expenses from schedules

**Modeling decision**:

- Client-side computation (not a backend endpoint)
- For each schedule where `type` ∈ {MONEY_IN, INTEREST, DIVIDEND}:
  1. Advance from `start_date` by one periodicity interval (skip first occurrence — it fires on `start_date`)
  2. Continue advancing until ≥ max(today, range_start)
  3. For each occurrence ≤ min(end_date, range_end): add to projected dataset
- Only future occurrences (≥ today) are included to avoid double-counting with realized transactions

**Currency model**:

- Projected amounts use `schedule.currency` and `schedule.total_value`
- No currency conversion is applied at projection time — amounts are in the schedule's native currency
- The frontend converts to `display_currency` when rendering charts/tables (same rule as all analytics)

**Rejected alternatives**:

- Backend projection endpoint → rejected: projection is pure date arithmetic. No DB queries needed beyond fetching schedules. Client-side is simpler and faster
- Including past occurrences → rejected: past occurrences have already been materialized as real transactions. Including them would double-count

**Entities affected**: `schedules` (read), `entities` (read for entity name lookup)

**UI pages**: Income page (`/income`)

**Constraints**:

- Occurrences must respect `end_date` if set
- `effectiveStart` = max(today, range_start) to avoid overlap with realized transactions
- Periodicity advancement must handle edge cases (Jan 31 → Feb 28)

---

## UC-17.1: Manual Edit Does Not Trigger Duplicate

**Trigger**: User edits a materialized transaction (e.g., changes date or amount) and the scheduler later runs again for the same occurrence date.

**Problem**: Without a separate tracking mechanism, the scheduler detects occurrences by matching `notes LIKE '%[schedule:N]%'` AND `timestamp LIKE '<date>%'` on the materialized transaction. Editing the date or removing the tag causes the scheduler to think the occurrence was never materialized, producing a duplicate.

**Solution**: A `schedule_occurrences` table records each materialized `(schedule_id, occurrence_date, transaction_id)` at creation time. The scheduler checks this table before creating any transaction — if a row exists, the fire is skipped. The occurrence record is never touched by user edits, so it remains accurate regardless of what happens to the underlying transaction.

| Scenario | Before (tag-based) | After (occurrence table) |
|---|---|---|
| User changes date | Duplicate created | Skipped (occurrence exists) |
| User changes amount | OK (date + tag match) | Skipped |
| User removes `[schedule:N]` tag | Duplicate created | Skipped |
| User deletes transaction | No duplicate | User can now re-create manually or scheduler fills on next run (if row is cleaned up) |

**Entities affected**: `schedule_occurrences` (write by scheduler, never touched by user)

**Implementation notes**:

- The `[schedule:N]` tag in `transactions.notes` is retained as a human-readable label but is no longer used for deduplication
- On transaction delete, the `schedule_occurrences` row can optionally be cleaned up (so the scheduler re-materializes) or left as-is (so the deletion is "permanent")
- Migration: existing tagged transactions are backfilled into `schedule_occurrences` at schema migration time using the tag and timestamp
