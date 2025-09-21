# Personal Finance & Investment Ledger

## Overview

This project is a personal accounting and investment tracking system implemented in Python with a Svelte-based frontend. It enables users to track cash, investments, and other financial movements across multiple entities (banks, brokers, wallets) and in multiple currencies. The system is designed with analytics and flexibility in mind, with a denormalized SQLite database, external API integration, and configurable visualization tools.

## Key Features

* **Configurable Base Currency:** Default JPY, but can be changed; system recalculates values based on historical FX rates.
* **Support for Multiple Currencies:** JPY, EUR, USD (extensible).
* **Actions Tracking:**

  * Money in / money out
  * Investment into specific instruments (stocks, ETFs, gold, currencies)
  * Scheduled operations (e.g., monthly ETF contributions, salary deposits)
* **Entity Support:** Track multiple accounts, brokers, wallets. Transfers between entities are supported, including fees (fixed, percentage, or both).
* **Taxes:** Start with fixed percentage taxes per income type, tagged as `FIXED` to support future complex calculation logic.
* **History Tracking:** Stores required price/FX data points for any transaction so that historical portfolio views remain accurate.
* **Runtime Valuation:** Displays portfolio based on most recent available data from API.
* **Precision:** 4 decimals for fiat currencies, 6 decimals for other assets.
* **Scheduling Options:** For scheduled actions, user can choose date adjustment policy:

  * Nearest business day
  * Previous closest business day
  * Next closest business day
  * Manual override
* **Charts & Analytics:** Embedded JS charting (Chart.js or similar) to visualize portfolio allocation, asset class breakdown, currency exposure, historical value vs. gold, etc.
* **Data Security:** Encrypted SQLite database and secret storage.
* **Backup & Sync:** Local and cloud backup supported.

## Architecture

* **Backend:** Python (FastAPI)
* **Frontend:** Pure HTML, CSS, JS with Svelte
* **Database:** SQLite (denormalized schema for analytics)
* **External API:** Used to fetch stock/ETF/currency values, fundamental data, and historical candles for accurate valuation and history reconstruction.

### Components

* **Core Service:** Handles transactions, schedules, calculations.
* **Scheduler:** Manages recurring operations.
* **API Client:** Connects to external price/FX API.
* **Analytics Engine:** Computes portfolio composition, historical performance, charts.
* **Web Interface:** Lightweight Svelte frontend.

## External API Interface

The system integrates with an external API to fetch market data, fundamentals, and FX information. This API will be provided and hosted separately.

### Base URL

`http://<host>:<port>`

### Endpoints

`<tag>` indicates a ticker or currency pair (e.g., `6723.T`, `ACX.MC`, `JPYUSD=X`).

* **GET `/symbol/<tag>`**: Fetch all available data for a symbol.

  * Includes company info, key statistics (market cap, P/E, margins), balance sheet, cash flow, earnings growth, and analyst estimates.
* **GET `/symbol/<tag>/<field>/`**: Fetch a specific field's value in JSON format.
* **GET `/symbol/<tag>/<field>/raw`**: Fetch a specific field's raw value.
* **GET `/symbol/historic/candle/<tag>`**: Download historical OHLCV data as CSV (5m candles, up to 60 days).

#### Example Outputs

* `curl http://localhost:5000/symbol/AAPL/ROE/`

```json
{"ROE": 1.7432836360316066}
```

* `curl http://localhost:5000/symbol/AAPL/ROE/raw`

```text
1.7432836360316066
```

* `curl http://localhost:5000/symbol/historic/candle/AAPL/raw`

```csv
Price,Close,High,Low,Open,Volume
Ticker,AAPL,AAPL,AAPL,AAPL,AAPL
Datetime,,,,,
2025-06-20 13:30:00+00:00,199.41079711914062,199.6300048828125,197.52999877929688,198.23500061035156,14021766
...
2025-09-15 19:55:00+00:00,236.75999450683594,236.7899932861328,235.86000061035156,235.9499969482422,2432989
```

### Available Data Categories

* **Corporate Info:** Name, address, industry, sector, website, employees, executives.
* **Market Data:** Price, range, volume, market cap, beta.
* **Financial Ratios:** P/E, forward P/E, P/B, margins, ROE, ROA, growth rates.
* **Balance Sheet:** Assets, liabilities, debt, equity, working capital.
* **P\&L & Cash Flow:** Revenue, EBITDA, net income, free cash flow, buybacks, debt issuance/repayment.
* **Analyst Estimates:** Target price (high/low/mean), rating trends, recommendation summary.

## Implementation Roadmap

1. ✅ **Project Setup**: FastAPI app, Svelte frontend, pyproject configuration.
2. **Database Schema**: Denormalized tables for transactions, schedules, entities, currencies, prices.
3. **API Client**: Implement connector for provided API endpoints.
4. **Transaction Engine**: Core logic to process money in/out, investments, transfers.
5. **Scheduler**: Background job to execute scheduled actions.
6. **Analytics**: Portfolio valuation, historical charts, FX normalization, display of key ratios (P/E, ROE, etc.).
7. **Frontend**: Svelte pages for dashboards, charts, transaction entry.
8. **Security**: SQLite encryption, key storage.
9. **Backup & Sync**: Local and optional cloud backup.

## Development Notes

* Designed to be single-user initially, but database schema includes `user_id` field for future multi-user support.
* Flexible CSV import planned for bulk loading transactions.
* Historical data is minimized to required points for analytics but API can refresh runtime prices.

---

This README serves as a living design document and development reference. All architectural decisions and feature definitions will be updated here as development progresses.

## Development Environment

This project uses the following tools and technologies for local development:

* [TODO] **Python dependency management:** [uv](https://github.com/astral-sh/uv) is used to create virtual environments and manage dependencies (`uv init`, `uv add fastapi`, etc.).
* **Backend server:** FastAPI with Uvicorn (run with `uv run uvicorn backend.app.main:app --reload`).
* **Frontend framework:** Svelte, using Vite as build tool and development server.
* **Frontend development:** The frontend is containerized. Developers do not need `npm` installed locally; instead, they can run the Vite dev server inside Docker.

### To add new Python dependencies

```bash
uv add <package>
docker compose build backend
```

### To add new JS dependencies

```bash
docker compose run --rm frontend npm install <package>
docker compose build frontend
```

### Running in Docker

The project provides a `docker-compose.yml` for running both backend (FastAPI) and frontend (Svelte + Vite) in development mode without requiring local npm installation.

To start:

```bash
docker compose up --build
```

* Backend: available at http://localhost:8000
* Frontend: available at http://localhost:5173

Both services mount the local source code as a volume, so changes are reflected live (hot reload enabled).

### Build and run frontend

```bash
docker compose run --rm frontend npm install
docker compose build frontend
docker compose up --build
```

### Run backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
pip install --upgrade pip
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
