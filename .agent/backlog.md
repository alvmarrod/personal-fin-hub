# Implementation Backlog

## Completed Alignment Work (Doc → Code)

All P0 alignment phases are complete. See Completed section below for details.

## Functional Debt (Pending Items)

| Priority | Item | Description |
|----------|------|-------------|
| P1 | Frontend Dashboard | Svelte 5 pages for dashboards, charts, transaction entry |
| P2 | Security | SQLite encryption, secret key storage |
| P2 | Backup & Sync | Local and optional cloud backup |

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
