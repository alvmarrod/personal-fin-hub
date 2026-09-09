# Timezone Model

Canonical reference for how the application handles timezones. Every use case and subsystem doc that involves timestamps, date-range filters, or time-dependent logic must link here.

## Two Classes of Time

| Class | Meaning | Examples | Rule |
|-------|---------|----------|------|
| **User-meaningful time** | Dates and times the user entered or that represent user-meaningful events | Manual transactions, balance snapshots, schedule calendar dates, materialized schedule transactions, fiscal periods | Interpreted in the **profile timezone** on input; stored as a **UTC instant**; displayed in the **profile timezone** |
| **System time** | Global market events independent of any user's locale | FX rate syncs (`currencies.timestamp`), price syncs (`prices.timestamp`), scheduler internal state | Stored and processed in **UTC** always; no profile-tz conversion |

## Storage

All timestamp columns store **naive UTC instants** — offset suffixes (`Z` or `+00:00`) are stripped on write. Columns: `transactions.timestamp`, `balance_snapshots.timestamp`, `manual_values.recorded_at`, `prices.timestamp`, `currencies.timestamp`, `schedule_occurrences.occurrence_date`. (`manual_values.recorded_at` defaults to SQLite UTC and is unused by the UI; `schedule_occurrences.occurrence_date` stores the profile-tz calendar date.)

Date-only columns (`schedules.start_date`, `schedules.end_date`, `fiscal_periods.start_date`/`end_date`) are timezone-free calendar dates interpreted in the profile timezone.

## Profile Timezone

Each profile carries a `timezone` field (IANA identifier, e.g. `Asia/Tokyo`). It is:

- **The interpretation zone** for all user-entered dates and times.
- **The display zone** for all timestamps shown to the user.
- Set in Settings; defaults to the browser-detected timezone on first use.

## Input Path (User → Database)

1. User enters a date/time (e.g. `2026-08-05 09:30`).
2. The frontend tags it with the profile timezone: `2026-08-05T09:30:00+09:00`.
3. The backend converts it to a UTC instant: `2026-08-05T00:30:00Z`.
4. The UTC instant is stored in SQLite.

## Display Path (Database → User)

1. Backend reads a UTC instant from SQLite (e.g. `2026-08-05T00:30:00Z`).
2. Backend (or frontend) converts it to the profile timezone: `2026-08-05T09:30:00+09:00`.
3. User sees `2026-08-05 09:30` (or `09:30 (JST)`).

## `now()` Semantics

The backend uses the **current UTC instant** for all time-dependent logic:

- UC-20: future transactions excluded from balance (`timestamp > now()`).
- UC-17: schedule projection (`today()` in profile-tz for day-boundary comparison).
- UC-38/39/41: scheduler fire evaluation.
- UC-46/47: price and rate sync scheduling.

`now()` is timezone-independent. The frontend converts it to the profile timezone only for display.

## Positional Adjustment Invariant (Reconciliation)

The `BALANCE_ADJUSTMENT` sentinel (UC-18/19) is defined as:

> At `ts − 1 day 23:59:59` in the profile timezone, converted to a UTC instant.

The invariant: no transaction may have `timestamp ≥ snapshot.timestamp`. The adjustment must remain strictly before the anchor. This is preserved by computing the adjustment in profile-tz first, then converting to UTC for storage.

## Date-Range Filters

A date-range filter (analytics, fiscal periods, UC-17 projection) is:

1. **Expressed in the profile timezone** (day boundaries at profile-tz midnight).
2. **Resolved to UTC instants** before querying the database.

This ensures a "day" means the same 24 hours regardless of the server's clock or the browser's local timezone. See UC-52 in `doc/uc_7_analytics_reads.md`.

## Scope of Changes

This model applies to every use case that involves timestamps, date ranges, or time-dependent comparisons. The cross-reference table below maps affected UCs:

| UC | File | What changes |
|----|------|-------------|
| UC-1 (Foundation CRUD) | `uc_1_foundation_crud.md` | Transaction `timestamp` input = profile-tz → UTC |
| UC-2 (Core Transactions) | `uc_2_core_transactions.md` | Injection `ts − 1 day 23:59:59` is profile-tz-derived UTC |
| UC-3 (Composite Transactions) | `uc_3_composite_transactions.md` | Composite dates in profile-tz → UTC |
| UC-4 (Schedules) | `uc_4_schedules.md` | Dates = profile-tz; materialized tx = JST date → UTC; UC-17 projection at profile-tz boundaries |
| UC-5 (Snapshots) | `uc_5_snapshots_balance.md` | UC-18/19/20 comparisons = UTC; snapshot input = profile-tz |
| UC-6 (Currency) | `uc_6_currency.md` | System-UTC (rates); no change |
| UC-7 (Analytics) | `uc_7_analytics_reads.md` | Date-range filters = profile-tz → UTC (see UC-52) |
| UC-8 (System-Initiated) | `uc_8_system_initiated.md` | UC-38/39/41 scheduler restamp to JST → UTC; UC-46/47 stay UTC |
| UC-9 (Planned) | `uc_9_planned.md` | Fiscal periods at profile-tz day boundaries |
| Calculations | `calculations.md` | Date-anchored metrics at profile-tz day boundaries |
