# Roadmap

## 🚨 Security & Reliability (blockers for internet exposure)

- [ ] **Authentication** — Add login/session management. Any internet-facing deployment needs this first.
- [ ] **Database backups** — Automated periodic backup of `data/finhub.db`. Single file corruption = total loss.
- [ ] **External API resilience** — Circuit breaker, retry logic, graceful fallback when the market price API is unreachable.

## 🚀 Features

- [ ] **CSV import** — Bulk-import transactions from bank/broker statements. Per-entity column mapping, duplicate detection, preview before commit.

## 🔧 Operations

- [ ] **`docker-compose.prod.yml`** — Production compose file (no source mounts, no `--reload`, no dev ports).
- [ ] **DB migration versioning** — Migration tracking table instead of ad-hoc `CREATE TABLE IF NOT EXISTS` + inline Python. Rollback support.
- [x] **Health check depth** — `/health` now verifies DB connectivity and external API reachability, returns per-component status + HTTP 503 on failure.
- [x] **Structured logging** — JSON log output via `python-json-logger`. Request IDs on every request (`X-Request-ID` header). `LOG_LEVEL` env var. Market API client logs at `DEBUG`. APScheduler noise suppressed.
- [ ] **Rate limiting** — Prevent brute-force or accidental API abuse.
- [x] **UTC timezone policy** — Backend: timestamps normalized to `YYYY-MM-DDTHH:MM:SS` on storage, all `datetime.now()` use UTC. Frontend: timezone selector in Settings with browser detection, shared `formatTimestamp()` utility.

## 🧪 Testing

- [x] **Frontend tests** — Vitest + Testing Library. 23 component tests across MetricCard, InfoTip, and Button. CI runs `bun run test` alongside build + svelte-check.
- [x] **E2E tests** — Playwright smoke tests verify all 14 pages load. CI runs `bun run test:e2e` with backend + frontend started automatically. Artifacts uploaded on failure.
- [x] **CI badges** — Backend coverage badge (77.5%) via shields.io. Auto-updated on `main` pushes (`make badges` locally). Frontend coverage blocked by Bun + Svelte 5 toolchain incompatibility.

## 📦 Release automation

- [x] **Changelog enforcement** — CI job + `make changelog-check` validates each changelog has a `[version]` section matching `pyproject.toml`/`package.json`.
- [x] **Release tag automation** — On push to `main` (new version), CI reads the version from `pyproject.toml`, creates a `vX.Y.Z` tag, and publishes a GitHub Release with combined changelog notes. Manual version bump only — no auto-semver.
- [x] **Conventional commits** — `commit-msg` hook enforces `type: description` format (`feat|fix|chore|docs|refactor|test|style|perf|ci|build`). No auto-generation.

## 🏗 Architecture (longer-term)

- [ ] **OpenTelemetry / tracing** — Request tracing across backend services, scheduler runs.
- [ ] **Config externalization** — Environment-based config instead of hardcoded values (`DB_PATH`, API URLs, ports).
- [ ] **Multi-user support** — Schema already has `user_id` fields. Data isolation, per-user API keys.
