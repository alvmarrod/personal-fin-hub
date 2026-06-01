# Implementation Backlog

## Functional Debt (Pending Items)

| Priority | Item | Description |
|----------|------|-------------|
| P0 | Transaction Engine | Core logic to process money in/out, investments, transfers with fees/taxes |
| P1 | Scheduler Service | APScheduler integration for recurring operations (schedules) |
| P1 | Analytics Engine | Portfolio valuation, historical performance, FX normalization |
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

## Implementation Roadmap

- [x] 1. Project Setup
- [x] 2. Database Schema
- [x] 3. API Client
- [ ] 4. Transaction Engine
- [ ] 5. Scheduler
- [ ] 6. Analytics
- [ ] 7. Frontend
- [ ] 8. Security
- [ ] 9. Backup & Sync