# Personal Finance & Investment Ledger

## Overview

This project is a personal accounting and investment tracking system implemented in Python with a Svelte-based frontend. It enables users to track cash, investments, and other financial movements across multiple entities (banks, brokers, wallets) and in multiple currencies. The system is designed with analytics and flexibility in mind, with a denormalized SQLite database, external API integration, and configurable visualization tools.

## Key Features

* **Configurable Base Currency:** Default EUR, but can be changed; system recalculates values based on historical FX rates.
* **Support for Multiple Currencies:** JPY, EUR, USD (extensible).
* **Actions Tracking:**

  * Money in / money out
  * Investment buy/sell with auto cash-injection (balance snapshots)
  * Dividend and interest income
  * Scheduled operations (e.g., monthly ETF contributions, salary deposits)
  * Transfers between entities with fees (fixed, percentage, or both)
* **Entity Support:** Track multiple accounts, brokers, wallets.
* **Taxes:** Fiscal exemptions with configurable rates and limits.
* **Price & FX Sync:** One-click sync for portfolio asset prices and currency exchange rates via external Market API.
* **Analytics Dashboard:** Portfolio value over time, asset allocation, cash flow, income breakdown, performance (realized/unrealized P&L).
* **History Tracking:** Stores required price/FX data points so historical portfolio views remain accurate.
* **Precision:** 4 decimals for fiat currencies.
* **Charts & Analytics:** Embedded JS charting (Chart.js) to visualize portfolio allocation, asset class breakdown, currency exposure, historical value vs. invested amount, segment labels.

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

## Development Notes

* Designed to be single-user initially, but database schema includes `user_id` field for future multi-user support.
* Flexible CSV import planned for bulk loading transactions.
* Historical data is minimized to required points for analytics but API can refresh runtime prices.

---

This README serves as a living design document and development reference. All architectural decisions and feature definitions will be updated here as development progresses.

## Development Environment

This project uses the following tools and technologies for local development:

* **Python Runtime:** [3.13](https://www.python.org/downloads/)
* **Package Manager:** [UV](https://github.com/astral-sh/uv) for Python, Bun for JS
* **Database:** SQLite (raw sqlite3, no ORM)
* **Testing:** unittest / pytest (708 tests)
* **Backend server:** FastAPI with Uvicorn
* **Frontend framework:** Svelte 5, using Vite as build tool

### Backend Module Structure

```
backend/
├── main.py           # FastAPI app entry point
├── routes/           # HTTP endpoint handlers
├── services/         # Business logic
├── models/           # Pydantic schemas
├── db/               # Database connection and queries
│   └── schema.sql    # SQLite schema
├── scheduler/        # APScheduler background jobs
├── tests/            # Unit and integration tests (708 tests, pytest)
```

### Pre-commit Hooks

This project uses pre-commit to run linting, formatting, and type checking before each commit.

**Setup:**

```bash
# Install pre-commit (if not already available)
cd backend
uv sync

# Install the git hooks
uv run pre-commit install
```

**Hooks:**

| Hook | Tool | Description |
|------|------|-------------|
| ruff check | [ruff](https://github.com/astral-sh/ruff) | Linting (pycodestyle, pyflakes, isort, bugbear, etc.) |
| ruff format | ruff | Code formatting |
| markdownlint | [markdownlint](https://github.com/igorshubovych/markdownlint-cli) | Markdown linting |
| mypy | [mypy](https://mypy-lang.org/) | Static type checking |

**Run manually on all files:**

```bash
uv run pre-commit run --all-files
```

To skip hooks temporarily (e.g., for WIP commits):

```bash
git commit -m "WIP" --no-verify
```

### To add new Python dependencies

```bash
cd backend
uv add <package>
```

### Run backend (local)

```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Run tests

```bash
cd backend
uv run python -m pytest tests/ -v
```

### Frontend development

The frontend runs via Docker to avoid local Node.js installation:

```bash
docker compose run --rm frontend bun install <package>
docker compose build frontend
```

### Running in Docker

```bash
docker compose up --build
```

* Backend: <http://localhost:8000>
* Frontend: <http://localhost:5173>

Both services mount local source code for hot reload.
