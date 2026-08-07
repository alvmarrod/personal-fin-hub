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
- [ ] **Structured logging** — JSON log lines with request IDs, error context, severity levels. Replace bare `print()`-style logs.
- [ ] **Rate limiting** — Prevent brute-force or accidental API abuse.
- [ ] **UTC timezone policy** — Enforce UTC for all stored timestamps, convert only at the presentation layer.

## 🧪 Testing

- [x] **Frontend tests** — Vitest + Testing Library. 23 component tests across MetricCard, InfoTip, and Button. CI runs `bun run test` alongside build + svelte-check.
- [x] **E2E tests** — Playwright smoke tests verify all 14 pages load. CI runs `bun run test:e2e` with backend + frontend started automatically. Artifacts uploaded on failure.
- [ ] **CI badges** — Coverage %, test count (requires `badges/` generation in CI).

## 📦 Release automation

- [x] **Changelog enforcement** — CI job + `make changelog-check` validates each changelog has a `[version]` section matching `pyproject.toml`/`package.json`.
- [x] **Release tag automation** — On push to `main` (new version), CI reads the version from `pyproject.toml`, creates a `vX.Y.Z` tag, and publishes a GitHub Release with combined changelog notes. Manual version bump only — no auto-semver.
- [x] **Conventional commits** — `commit-msg` hook enforces `type: description` format (`feat|fix|chore|docs|refactor|test|style|perf|ci|build`). No auto-generation.

## 🏗 Architecture (longer-term)

- [ ] **OpenTelemetry / tracing** — Request tracing across backend services, scheduler runs.
- [ ] **Config externalization** — Environment-based config instead of hardcoded values (`DB_PATH`, API URLs, ports).
- [ ] **Multi-user support** — Schema already has `user_id` fields. Data isolation, per-user API keys.
