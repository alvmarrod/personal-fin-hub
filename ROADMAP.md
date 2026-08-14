# Roadmap

## 🚨 Security & Reliability (blockers for internet exposure)

- [discarded] **Authentication** — Add login/session management. Any internet-facing deployment needs this first. **Decision (2026-08-11): not implementing — staying with identification only, not authorization.** Profile scoping via `X-Profile-ID` (verified to reference an existing profile) is the intended posture for the foreseeable future; the per-profile password is a client-side unlock UX, not an API-level auth barrier. Revisit before any internet exposure.
- [x] **Database backups** — Automated periodic backup of `data/finhub.db` via the stdlib `sqlite3.Connection.backup()` API. Daily at `BACKUP_CRON` in `BACKUP_TIMEZONE`, startup catch-up, pre/post migration backups, retention pruning, and a guarded `restore` CLI. Verified after creation; `/health` reports backup status. See `doc/subsystems/backups.md`.
- [x] **External API resilience** — Circuit breaker, retry logic, graceful fallback when the market price API is unreachable. **Shipped (2026-08-11)**: retry (backoff+jitter), per-`base_url` circuit breaker, fail-fast sync loops, health reporting, and a stale-data UI signal on asset pages (same pattern as the income forex note). Design: `doc/subsystems/market_api_client.md`.
- [x] **Single-command Docker deployment** — [`yfinance-api`](https://github.com/alvmarrod/yfinance-api) integrated as a Compose service. `docker compose up -d` starts all three services with health-check ordering. No separate clone/config needed. **Shipped (2026-08-11)**.

## 🚀 Features

- [x] **Profiles (multitenancy)** — Local multi-profile support. Create / switch / logout / delete profiles; optional per-profile password (pbkdf2, stdlib). Migration creates a passwordless default profile and assigns all existing data to it. Every profile supports renaming. Delete removes only the profile's own data (never shared market reference data) and requires double confirmation — the second prompt asks the user to type the localized word for "delete" (`DELETE`/`BORRAR` per current language). Market reference data (currencies, market_assets, prices, stock_splits) stays shared; user-created data (entities, transactions, fees, taxes, portfolio_assets, balance_snapshots, schedules, occurrences, manual_values, fiscal_exemptions) becomes profile-scoped via `profile_id`.
- [x] **Update availability check** — Backend endpoint `GET /api/v1/updates` compares the installed backend/frontend versions against the latest GitHub Releases (`backend/` / `frontend/` prefixes), cached and fail-open. The frontend shows a dismissible warning badge (linking to the release) when a newer release exists. See `doc/subsystems/api_endpoints.md` + `doc/subsystems/UI.md`.
- [ ] **CSV import** — Bulk-import transactions from bank/broker statements. Per-entity column mapping, duplicate detection, preview before commit.

## 🔧 Operations

- [x] **`docker-compose.prod.yml`** — Compose override that removes `--reload` and source mount from backend, remaps frontend to port 40080. Used as `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
- [x] **DB migration versioning** — `db/migrations/` with 7 numbered modules. `schema_migrations` table tracks applied versions. Runner applies only unapplied migrations in order. Replaces ad-hoc inline migrations.
- [x] **Health check depth** — `/health` now verifies DB connectivity and external API reachability, returns per-component status + HTTP 503 on failure.
- [x] **Structured logging** — JSON log output via `python-json-logger`. Request IDs on every request (`X-Request-ID` header). `LOG_LEVEL` env var. Market API client logs at `DEBUG`. APScheduler noise suppressed.
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
- [ ] **Multi-user support** — Internet-facing auth: login, session management, per-user API keys. Note: the schema does NOT yet have `user_id` columns (verified 2026-08-08) — data isolation groundwork is being laid by the local **Profiles** feature above.
