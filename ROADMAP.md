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

- [ ] **Frontend tests** — 0 tests today vs 719 backend. At minimum: component render tests + API mock integration.
- [ ] **E2E tests** — Critical user journeys (create transaction → see in dashboard → edit → delete).
- [ ] **CI badges** — Coverage %, test count (requires `badges/` generation in CI).

## 📦 Release automation

- [ ] **Changelog enforcement** — CI check that changelog is updated for the current version.
- [ ] **Release tag automation** — CI job to create tags + GitHub Release from changelog entries.
- [ ] **Conventional commits** — Enforce commit message format for automated changelog generation.

## 🏗 Architecture (longer-term)

- [ ] **OpenTelemetry / tracing** — Request tracing across backend services, scheduler runs.
- [ ] **Config externalization** — Environment-based config instead of hardcoded values (`DB_PATH`, API URLs, ports).
- [ ] **Multi-user support** — Schema already has `user_id` fields. Data isolation, per-user API keys.
