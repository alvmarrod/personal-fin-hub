# Implementation Backlog

## Functional Debt (Unimplemented Requirements)

| Priority | Item | Description |
|----------|------|-------------|
| P0 | Backend module structure | Create layered architecture (routes/, services/, models/, db/) |
| P1 | API Client | Implement connector for external market data API endpoints |
| P2 | Transaction Engine | Core logic to process money in/out, investments, transfers with fees/taxes |
| P2 | Scheduler Service | APScheduler integration for recurring operations (schedules) |
| P2 | Analytics Engine | Portfolio valuation, historical performance, FX normalization |
| P2 | Frontend Dashboard | Svelte 5 pages for dashboards, charts, transaction entry |
| P3 | Security | SQLite encryption, secret key storage |
| P3 | Backup & Sync | Local and optional cloud backup |

## Implementation Roadmap (from README)

- [x] 1. Project Setup: FastAPI app, Svelte frontend, pyproject config
- [x] 2. Database Schema: Denormalized tables
- [ ] 3. API Client: External market data connector
- [ ] 4. Transaction Engine: Core processing logic
- [ ] 5. Scheduler: Background job for recurring actions
- [ ] 6. Analytics: Portfolio composition, charts, FX normalization
- [ ] 7. Frontend: Svelte UI for all features
- [ ] 8. Security: Encryption, key storage
- [ ] 9. Backup & Sync: Local/cloud backup