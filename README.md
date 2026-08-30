# Personal Finance & Investment Ledger

<p align="center"><img src="finhub.png" width="120" alt="finhub logo"></p>

![Version](https://img.shields.io/github/v/tag/alvmarrod/personal-fin-hub?label=version)
[![CI](https://github.com/alvmarrod/personal-fin-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/alvmarrod/personal-fin-hub/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/alvmarrod/personal-fin-hub/main/badges/coverage.json)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

finhub is a personal accounting and investment tracking system. It records cash, investments, and other money movements across entities (banks, brokers, wallets) and currencies.

The backend is Python/FastAPI. The frontend is Svelte. Data lives in a denormalized SQLite database tuned for analytics and historical reconstruction, with prices and FX rates synced from an external market API.

## Key Features

- **Configurable base currency** — EUR by default. Historical FX rates recalculate all values.
- **Multi-currency** — JPY, EUR, USD, extensible.
- **Full action coverage** — money in/out, buy/sell with auto cash-injection from balance snapshots, dividends, interest, transfers across entities with fees (fixed, percentage, or both), and scheduled operations (monthly ETF contributions, salary deposits).
- **Taxes** — fiscal exemptions with configurable rates and limits.
- **Market sync** — one-click refresh of prices and FX rates via the external Market API.
- **History tracking** — stores the price and FX points required to keep historical views accurate.
- **Analytics dashboard** — portfolio value over time, asset allocation, cash flow, income breakdown, realized and unrealized P&L, asset-class and currency exposure, and segment labels via embedded Chart.js.
- **Precision** — 4 decimal places for fiat currencies.

## Tech Stack

- **Backend** — Python 3.13, FastAPI, APScheduler, SQLite (raw sqlite3, no ORM).
- **Frontend** — Svelte 5, Chart.js, built with Vite, served by nginx.
- **Market API** — [yfinance-api](https://github.com/alvmarrod/yfinance-api) for prices, fundamentals, FX, and historical candles, wrapped behind a circuit breaker with retry.

## Quick Start (Docker)

Run the backend and frontend:

```bash
docker compose up -d
```

Start services: backend on port 8000, frontend on port 5173. Images are self-contained: the source is baked in at build time, and only `backend/data` and `backend/config.json` (read-only) are mounted.

To also start the bundled Market API, enable the `external` profile:

```bash
docker compose --profile external up -d
```

The Market API listens on port 5001 (host) and 5000 (container). It keeps a cache in the `market_cache` named volume, and the backend connects to it over the internal DNS as `http://market-api:5000`.

### Use an existing Market API instance

If the Market API runs on another host or port, change `market_api.base_url` in [backend/config.json](backend/config.json), then start without the bundled service:

```bash
docker compose up -d backend frontend
```

The backend starts even if the API is unreachable. The circuit breaker and retry handle outages.

### Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The production override runs the backend without `--reload`, drops the source mount, and remaps the frontend to port 40080.

## Local Development

Requirements: Python 3.13, [UV](https://github.com/astral-sh/uv), Bun.

| Task | Command |
|------|---------|
| Backend with live reload | `make dev-run-backend` |
| Backend tests | `make test-backend` |
| Frontend tests and checks | `make test-frontend` |
| Backend lint and types | `make lint-backend` |
| Frontend lint | `make lint-frontend` |
| Full test suite | `make test` |

Run the backend tests directly:

```bash
cd backend && uv run python -m pytest
```

Add a Python dependency:

```bash
cd backend && uv add <package>
```

The frontend toolchain runs via Docker, so no local Node.js install is needed:

```bash
docker compose run --rm frontend bun install <package>
docker compose build frontend
```

## Configuration

- [backend/config.json](backend/config.json) — runtime settings. Most important is `market_api.base_url`.
- `BACKUP_CRON` — backup schedule as `HH:MM` (default `03:00`).
- `BACKUP_TIMEZONE` — IANA timezone for the backup schedule. It falls back to `TZ`, then container local time.
- `LOG_LEVEL` — backend log level (default `INFO`).

## Project Layout

```
backend/    FastAPI application: routes, services, models, db, scheduler, tests
frontend/   Svelte 5 application
doc/        Design docs, use cases, and subsystem specifications
scripts/    Release and maintenance utilities
badges/     Generated coverage badges
```

## Documentation

- [Design docs](doc/) — HLD, use cases, calculations, subsystem specs.
- [Backups](doc/subsystems/backups.md)
- [Market API client](doc/subsystems/market_api_client.md)
- [API endpoints](doc/subsystems/api_endpoints.md)
- [Frontend](doc/subsystems/UI.md)
- [Roadmap](ROADMAP.md)

## Backups

SQLite backups run automatically with the stdlib `backup()` API, are verified after creation, and are pruned to the newest N files.

- **Daily** — `backup_daily` runs at `BACKUP_CRON` (default `03:00`), with startup catch-up if the time already passed.
- **Migrations** — pre/post backups on schema migration.
- **Recovery** — `make backup` and `make restore BACKUP=<file>`. Restore refuses while the backend runs.
- **Health** — `/api/v1/health` reports backup status (`ok`/`stale`/`never`/`disabled`).

Files land in `BACKUP_DIR` (default `<db dir>/backups`) as `finhub.db-YYYYMMDD-HHMMSS.bak`. See [doc/subsystems/backups.md](doc/subsystems/backups.md) for the full design.

## Contributing

Pre-commit runs ruff, mypy, pytest, svelte-check, i18n validation, and markdownlint, and enforces conventional commit messages. See [.pre-commit-config.yaml](.pre-commit-config.yaml).

```bash
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit run --all-files
```

## License

MIT — see [LICENSE](LICENSE).
