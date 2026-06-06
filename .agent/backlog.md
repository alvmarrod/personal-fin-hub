# Implementation Backlog

## Pending Alignment Work (Doc → Code)

| Priority | Phase | Item | Description |
|----------|-------|------|-------------|
| P0 | A | Balance Snapshots — Backend | ✅ Done |
| P0 | B | Delete Pre-Checks — All Entities | Every hard-delete service verifies FK dependents and returns 409 if blocked. Affects: entity, market_asset, portfolio_asset, transaction, fiscal_exemption, currency_code, currency_pair |
| P0 | C | Entity Soft-Delete — Schedule Check | Verify no active schedules before allowing soft-delete (new query + pre-check) |
| P0 | D | Schedule Model Refactor | Replace `linked_transaction_id` with embedded fields (`total_value`, `currency`, `entity_id`, `type`, `notes`). Rewrite `_clone_tx` to build from embedded fields. Update `POST /schedules/full` (no longer needs nested TransactionCreate) |
| P0 | E | Frontend Schedule Refactor | Update `income/+page.svelte` to work with new embedded schedule model (remove `linked_transaction_id` dependency) |
| P0 | F | Tests | New tests for balance snapshots, delete pre-checks, entity soft-delete schedule check, schedule refactor |

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

## Implementation Roadmap

- [x] 1. Project Setup
- [x] 2. Database Schema
- [x] 3. API Client
- [x] 4. Transaction Engine
- [x] 5. Scheduler
- [x] 6. Analytics
- [ ] 7. **Doc→Code Alignment** (Phases A-F)
- [ ] 8. Frontend (full)
- [ ] 9. Security
- [ ] 10. Backup & Sync
