# Architecture Overview

## Technology Stack

- **Runtime:** Python 3.13
- **Frontend:** Svelte 5
- **Package Manager:** Bun (frontend)
- **Database:** SQLite (denormalized)
- **Scheduler:** APScheduler (in-process)
- **Backend Framework:** FastAPI

## Architecture Pattern

Layered architecture: Routes → Services → Models → Database

## Component Diagram

```text
+-------------------------------------------------------------+
|                      Frontend (Svelte 5)                   |
|                    (Bun + Vite dev server)                 |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    FastAPI Backend (Layered)                |
+-------------------------------------------------------------+
|  Routes         |  Services      |  Models    |  Scheduler  |
|  /transactions |  currency_svc  |  pydantic  | APScheduler|
|  /entities     |  transaction_svc            |             |
|  /assets       |  analytics_svc              |             |
|  /schedules    |  pnl_rules (fiscal P&L)     |             |
|  /fiscal-...   |  fiscal_period_svc          |             |
|                |  api_client                 |             |
|                |  api_resilience             |             |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|  SQLite (denormalized)                                     |
|  Tables: profiles, market_assets, portfolio_assets,        |
|          transactions, entities, currencies, prices,      |
|          schedules, transaction_fees, transaction_taxes,  |
|          schedule_occurrences, scheduler_state,           |
|          fiscal_exemptions, fiscal_periods, tax_rates,    |
|          balance_snapshots                                |
|  Ownership tables carry profile_id; market reference      |
|  tables are shared                                       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   External Market API                       |
|           (http://<host>:<port>/symbol/<tag>)              |
+-------------------------------------------------------------+
```text

## Component Responsibilities

| Component | Responsibility |
|-----------|-----------------|
| `routes/` | HTTP endpoints, request validation, response serialization |
| `services/` | Business logic, calculations, API client calls |
| `models/` | Pydantic schemas, database models |
| `scheduler/` | APScheduler job management for recurring operations |
| `db/` | SQLite connection, migrations, queries |

## Data Flow

1. Client -> FastAPI route -> Service -> Database
2. Scheduler -> APScheduler -> Service -> Create transaction
3. Analytics -> API Client -> External Market API -> Cache prices -> Serve to frontend

> The API client is wrapped by a retry + circuit-breaker layer
> (`services/api_resilience.py`); on an API outage the app keeps serving last
> known good data, with holdings responses signaling price source/age to the UI.
> See `doc/subsystems/market_api_client.md`.

> Update availability is checked by the backend against GitHub Releases
> (`services/update_svc.py`, `GET /api/v1/updates`), cached and fail-open; the
> frontend renders a dismissible warning badge when a newer backend/frontend
> release exists. See `doc/subsystems/api_endpoints.md` and
> `doc/subsystems/UI.md`.

## Profiles (Multitenancy)

The application supports multiple isolated profiles. Data is split into two classes:

| Class | Tables | Scoping |
|-------|--------|---------|
| **Shared market reference data** | `currencies`, `market_assets`, `prices`, `stock_splits`, `scheduler_state` | Not profile-scoped; one global copy |
| **User-created (owned) data** | 10 tables (transactions, entities, portfolio_assets, schedules, transaction_fees, transaction_taxes, schedule_occurrences, fiscal_exemptions, balance_snapshots, manual_values) | Each row carries a `profile_id INTEGER REFERENCES profiles(id)` |

- **Request scoping**: the frontend sends the active profile id via the `X-Profile-ID` header; a FastAPI dependency resolves it and the whole route→service→query chain filters by `profile_id` (incl. PK lookups and dependent tables), preventing cross-profile access.
- **Identification only, no authorization**: per-profile passwords are a client-side unlock UX (stdlib `pbkdf2_hmac`), not an API-level auth barrier. There is no login/session management — revisit before any internet exposure.
- **Unlock flow**: `POST /profiles/{id}/unlock` verifies the password server-side; the frontend keeps the unlocked state in `sessionStorage`. The frontend shows a profile picker when no profile is active.
- **Deletion**: `DELETE /profiles/{id}` removes only the profile's own rows across the 10 ownership tables (child-first for FK order) and never shared data; deleting the last remaining profile is rejected (409).
- **Timezone**: each profile carries a `timezone` field (IANA identifier, e.g. `Asia/Tokyo`). The profile timezone determines how user-entered dates are interpreted and how stored UTC timestamps are displayed. See `doc/timezone_model.md`.
- **Migration `008_profiles`**: adds `profile_id` to the ownership tables and backfills existing rows to the passwordless default profile. A verification-based runner repairs legacy DBs that were previously bootstrapped as migrated without actually running the migration.

See `doc/subsystems/database.md`, `doc/subsystems/api_endpoints.md`, and `doc/subsystems/UI.md` for details.

## Currency Rate Architecture

The system distinguishes two types of currency rates with separate storage and purpose:

| Type | Table | Purpose | Source |
|------|-------|---------|--------|
| **Market Reference Rate** | `currencies` | Portfolio valuation, historical analytics, benchmark | External market data (periodic) |
| **Transaction-Applied Rate** | `transactions.fx_rate` | Actual cash flow, broker-applied rate incl. spread | Recorded per transaction from broker conversion |

See `doc/subsystems/database.md` for full details.

## Timezone Architecture

The system uses **UTC as the canonical storage representation** for all timestamps. Two classes of time exist, with different handling:

| Class | Tables | Rule |
|-------|--------|------|
| **User-meaningful time** | `transactions.timestamp`, `balance_snapshots.timestamp`, `manual_values.recorded_at`, `schedule_occurrences.occurrence_date`, `schedules.start_date`/`end_date` | Interpreted in the profile timezone on input; converted to UTC for storage; converted back to the profile timezone on display |
| **System time** | `prices.timestamp`, `currencies.timestamp`, `scheduler_state` | Stored and processed in UTC always; no profile-tz conversion |

**Input path**: a user enters a date/time in the profile timezone (e.g. `Asia/Tokyo`). The backend resolves it to a UTC instant and stores it.

**Display path**: the frontend reads a UTC instant and converts it to the profile timezone before rendering.

**`now()` semantics**: the backend uses the current UTC instant for all time-dependent logic (future-transaction exclusion, schedule evaluation). `now()` is timezone-independent.

**Positional adjustment invariant**: `BALANCE_ADJUSTMENT` records at `ts − 1 day 23:59:59` (the reconciliation sentinel per UC-18/19) are defined in the profile timezone, then converted to UTC for storage. They must remain strictly before their anchor timestamp.

See `doc/timezone_model.md` for the full canonical reference.
