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

Decisions: market reference data (currencies, market_assets, prices, stock_splits) stays shared. User-created data gets `profile_id`. Passwords: stdlib pbkdf2_hmac, no new deps. Sessions: lightweight unlock — server verifies password at unlock; frontend holds unlocked state in sessionStorage; no sessions table. Deletion: removes only the profile's own data, never shared data; double confirmation with second prompt requiring the user to type the localized word for "delete" (`DELETE`/`BORRAR` per active language).

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
