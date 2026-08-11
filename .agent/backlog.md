# Implementation Backlog

## Completed Alignment Work (Doc → Code)

All P0 alignment phases are complete. See Completed section below for details.

## Functional Debt (Pending Items)

| Priority | Item | Description |
|----------|------|-------------|
| P1 | Frontend Dashboard | Svelte 5 pages for dashboards, charts, transaction entry |
| P2 | Security | SQLite encryption, secret key storage |
| P2 | Backup & Sync | Local and optional cloud backup |

## Profiles (Multitenancy) — Planned

Decisions: market reference data (currencies, market_assets, prices, stock_splits) stays shared. User-created data gets `profile_id`. Passwords: stdlib pbkdf2_hmac, no new deps. Sessions: lightweight unlock — server verifies password at unlock; frontend holds unlocked state in sessionStorage; no sessions table. **Standing decision (2026-08-11): identification only, no authorization.** Profile scoping via `X-Profile-ID` header is the intended posture; per-profile password is client-side unlock UX, not an API-level auth barrier. No login/session management in scope — revisit only before internet exposure. Deletion: removes only the profile's own data, never shared data; double confirmation with second prompt requiring the user to type the localized word for "delete" (`DELETE`/`BORRAR` per active language).

- [x] **Phase 1 — Schema & migration `008_profiles.py`**: create `profiles` table (id, name UNIQUE, password_hash, created_at, updated_at); insert passwordless default profile; add `profile_id` to 10 ownership tables with backfill to default profile + indexes.
- [x] **Phase 2 — Backend profiles API**: `GET /profiles` (list, no hashes), `POST /profiles` (create, optional password), `POST /profiles/{id}/unlock` (verify password), `PATCH /profiles/{id}` (rename), `DELETE /profiles/{id}` (cascade-delete only the profile's rows across the 10 ownership tables, child-first for FK order; reject deleting the last remaining profile). pbkdf2 hash/verify service.
- [x] **Phase 3 — Profile-scoped data access**: FastAPI dependency reads `X-Profile-ID` header; every route→service→query chain for the 10 ownership tables filters by profile_id (incl. PK lookups and dependent tables) to prevent cross-profile access.
- [x] **Phase 4 — Scheduler per-profile**: catch-up and job execution iterate all profiles' schedules; generated transactions get correct profile_id. (`_scoped_profile` in `backend/scheduler/scheduler.py`; 6 new tests in `backend/tests/test_scheduler.py`; full suite `850 passed`, ruff + mypy clean.)
- [x] **Phase 5 — Frontend profiles**: profile store (sessionStorage), picker screen when no active profile, Header shows profile + switch/logout, Settings section for create/rename/delete (delete flow = first confirm dialog, then localized type-in `DELETE`/`BORRAR` confirm), api client sends `X-Profile-ID`.
- [ ] **Phase 6 — Tests + docs**: profile CRUD/unlock/delete tests (incl. last-profile protection + shared-data preservation), cross-profile isolation tests, migration backfill test, scheduler multi-profile test, picker/store frontend tests, E2E create→switch→logout→delete. Update architecture_overview + subsystem docs.

## Completed

- [x] Project Setup: FastAPI app, Svelte frontend, pyproject config
- [x] Database Schema: Denormalized tables (10 tables)
- [x] API Client: MarketAPIClient with httpx, endpoints, tests
- [x] Backend module structure: routes/, services/, models/, db/ layered architecture
- [x] Docker orchestration: docker-compose.yml, frontend Dockerfile
- [x] Documentation: architecture_overview.md, subsystem docs for db, api, market client
- [x] **Transaction Engine** (Slice 4): Core CRUD for all 10 resources + composite endpoints (full transaction, batch, transfer, schedule full) — 96 tests
- [x] **Scheduler Service** (Slice 5): APScheduler integration, job runtime, auto-sync on schedule CRUD — 18 tests
- [x] **Analytics Engine** (Slice 6): 3 slices (Holdings, Cash Flow, Performance) — 9 endpoints, ~83 tests
- [x] **Documentation Alignment**: workflow.md, database.md, api_endpoints.md, UI.md updated with balance snapshots, delete pre-check policy, schedule embedded fields, dependency tree fix
- [x] **Phase A — Balance Snapshots**: Schema, models, queries, service, routes — 49 tests
- [x] **Phase B — Delete Pre-Checks**: 6 `*_has_dependents` queries, 6 error classes, route catches → 409 — 6 route tests
- [x] **Phase C — Entity Soft-Delete Schedule Check**: `_clone_tx` checks `get_entity()` before cloning — 1 test
- [x] **Phase D — Schedule Model Refactor**: Embedded fields (`entity_id`, `currency`, `type`, `total_value`, `notes`) replace `linked_transaction_id` across schema, queries, models, services, scheduler, routes, tests
- [x] **Phase E — Frontend Schedule Refactor**: `AddIncomeModal.svelte` sends embedded fields directly; `+page.svelte` reads `s.type`, `s.entity_id`, `s.total_value` from schedule (no linked transaction lookup)

## Implementation Roadmap

- [x] 1. Project Setup
- [x] 2. Database Schema
- [x] 3. API Client
- [x] 4. Transaction Engine
- [x] 5. Scheduler
- [x] 6. Analytics
- [x] 7. **Doc→Code Alignment** (Phases A-F)
- [ ] 8. Frontend (full)
- [ ] 9. Security
- [ ] 10. Backup & Sync

## Backup & Sync — Planned

**Scope**: local automated backups only (cloud sync = separate follow-up). Single-file SQLite (`backend/data/finhub.db`) — one-file corruption = total loss, so backups are online-safe, verified, and self-pruning.

Decisions:

- **Online-safe**: stdlib `sqlite3.Connection.backup()` API (consistent under concurrent writes; plain file `cp` is unsafe in rollback-journal mode).
- **Schedule**: daily at `BACKUP_CRON` (default `03:00`) in `BACKUP_TIMEZONE` (IANA, e.g. `Asia/Tokyo`; default = container local tz — **must be set**; the frontend timezone selector is display-only and invisible to the backend).
- **Startup catch-up**: on startup, if past the daily time in `BACKUP_TIMEZONE` and no backup exists for the current day, create one **before anything else** (pre-migration state).
- **Migration backups**: if migrations are applied to an existing DB, exactly two backups around them — one pre-migration (reused from the daily catch-up if it already ran this boot) and one post-migration. Skipped on fresh installs.
- **Retention**: `BACKUP_RETENTION` (default 7) newest, pruned after each backup.
- **Location**: `BACKUP_DIR` (default `<db dir>/backups`), filenames `finhub.db-YYYYMMDD-HHMMSS.bak`, mode `0600`.
- **Config**: `BACKUP_ENABLED` (default on), `BACKUP_DIR`, `BACKUP_TIMEZONE`, `BACKUP_CRON`, `BACKUP_RETENTION`.
- **Restore**: out-of-band CLI `make restore BACKUP=<file>` (refuses while `/health` is reachable, verifies integrity after copy). No API endpoint.
- **Observability**: structured logs per backup (start/success/size/duration/prune); `/health` reports `backup` status (`ok`/`stale`/`never`/`disabled`, public-safe, informational).

Contract: `backend/services/backup_svc.py`, `backend/scheduler/scheduler.py` (`init_scheduler`), `backend/main.py` (lifespan), `backend/routes/health.py`. Doc: `doc/subsystems/backups.md`.

Phases:

- [ ] **Phase 1 — backup_svc + config**: `create_backup`/`verify_backup`/`prune_backups`/`list_backups`/`latest_backup`/`is_daily_due`/`backup_info`/`restore_from_backup`; env config (ENABLED/DIR/TIMEZONE/CRON/RETENTION).
- [ ] **Phase 2 — startup + scheduler wiring**: `_run_migrations`/`init_db` return applied versions + fresh flag; lifespan runs daily catch-up (pre-everything) and pre/post migration backups; `init_scheduler` registers daily job with `BACKUP_TIMEZONE`.
- [ ] **Phase 3 — observability + ops**: `/health` backup status; CLI `scripts/backup.py` + `scripts/restore.py`; `make backup` / `make restore`.
- [ ] **Phase 4 — tests + docs**: backup service unit tests (validity, retention, daily-due with mocked clock, restore, tz/config defaults), migration-return tests, scheduler job-count tests updated; `doc/subsystems/backups.md`; ROADMAP/backlog/changelog/version bump.

Out of scope (follow-ups): cloud/remote sync, encryption at rest, corruption alarm.

---

## External API Resilience — Planned

**Scope**: make the app resilient to a slow, flaky, or unreachable Market API. Retry + circuit breaker + fail-fast loops + health reporting (backend), plus a stale-data UI signal on asset pages (same pattern as the income forex note). Scheduled price/rate refresh is a **separate** item — see below.

Decisions:

- **Single choke point**: resilience lives inside `MarketAPIClient._request()` (new `services/api_resilience.py`). Public interfaces of `routes/market.py`, `currency_svc.sync_rates`, `health.py` stay unchanged.
- **Retry**: exponential backoff ±20% jitter. Retried: `ConnectError`, `TimeoutException`, HTTP `5xx`, `429` (honors `Retry-After`). Never retried: other `4xx` (incl. `404` → `MarketAPINotFound` stays authoritative). Defaults 3 attempts, 0.5s base, 10s max.
- **Circuit breaker**: per-`base_url`, in-process, thread-safe (request threads + scheduler share it). `closed → open → half-open → closed`. Open = fail fast with `MarketAPIUnavailable` (no timeout stall). Half-open = 1 trial request. Defaults: 5 failures → open, 60s cooldown.
- **Fail-fast loops**: `sync-prices` / `currencies/sync` short-circuit when the breaker is open → return `circuit_open: true` + `skipped` entries instead of `N × timeout`. Partial-failure per-pair/symbol error shape preserved.
- **Health**: `/health` reports circuit state + `last_success_at`; health must not hammer an open circuit.
- **Stale-data signal**: `HoldingLine` gains `price_source` (`market-api`|`transaction-fallback`|`manual`|`none`) + `price_as_of`; asset pages render a callout in the income/cash-flow rate-warning style, with EN/ES i18n keys. Reads already fall back (`prices` row → latest INVESTMENT_BUY unit_price → none/manual) — this adds the stale-data signal on top.
- **Config**: `config.json` → `market_api.*`: `retry_attempts`, `retry_base_delay`, `retry_max_delay`, `circuit_failure_threshold`, `circuit_cooldown_seconds`.

Contract: `backend/services/api_resilience.py`, `backend/services/api_client.py` (`_request`), `backend/routes/market.py` + `backend/services/currency_svc.py` (loop fail-fast), `backend/routes/health.py`, `backend/models/models.py` (`HoldingLine`), `backend/services/analytics_svc.py` (price_source/as_of), frontend asset pages + `i18n`. Doc: `doc/subsystems/market_api_client.md`.

Phases:

- [x] **Phase 1 — retry**: transport-level retry with backoff+jitter in `_request`; `MarketAPIClient` config wiring; tests (transient retried, 4xx not retried, 429/Retry-After, backoff sequence).
- [x] **Phase 2 — circuit breaker**: `api_resilience.py` state machine (thread-safe); `_request` integration; fail-fast in `sync-prices`/`currencies/sync`; tests (threshold→open, half-open trial, recovery, open fail-fast, loop short-circuit).
- [x] **Phase 3 — health + stale-data signal**: `/health` circuit fields; `HoldingLine` `price_source`/`price_as_of`; asset page callout + EN/ES i18n; tests (health shape, holdings metadata, frontend component).
- [x] **Phase 4 — docs + release**: ROADMAP/backlog/changelog/version bump, full suite green. Shipped as backend `0.9.0` + frontend `0.7.0`; changelogs updated; ROADMAP marks the item done; backend suite `932 passed`, frontend `86 passed`, ruff + mypy clean.

Out of scope (separate item): scheduled price/rate refresh job, response caching, rate limiting, resilience of the external service itself.

## Scheduled Price/Rate Refresh — Planned (separate item)

Automatic periodic refresh of prices and currency rates via APScheduler (system-initiated, uc-8 style). Runs on a cron; skips the cycle when the circuit breaker is open and retries next scheduled run; reconciles with the fail-fast + stale-data design above. Contract/doc follow when this item is picked up.
