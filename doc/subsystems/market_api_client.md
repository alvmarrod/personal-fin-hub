# Subsystem: External Market API Client

## Base URL

Configurable in `backend/config.json` under `market_api.base_url`. Default: `http://<host>:5001`

## Endpoints

### Health & Monitoring

- **GET /health**: Health check

### Symbol Data

- **GET /symbol/<tag>**: Fetch all available data for a stock symbol
- **GET /symbol/<tag>/<field>/**: Fetch specific field's value as JSON
- **GET /symbol/<tag>/<field>/raw**: Fetch raw field value
- **GET /symbol/historic/candle/<tag>**: Historical OHLCV data as CSV (5m candles, up to 60 days)

**Examples:**

```bash
# Health check
curl http://<host>:5001/health

# Fetch specific field (ROE)
curl http://<host>:5001/symbol/AAPL/ROE/
# Response: {"ROE": 1.7432836360316066}

# Fetch raw field value
curl http://<host>:5001/symbol/AAPL/ROE/raw
# Response: 1.7432836360316066

# Historical candles
curl http://<host>:5001/symbol/historic/candle/AAPL/raw
# Response CSV: DateTime,Close,High,Low,Open,Volume
```text

## Queryable Fields by Asset Type

### Stocks

| Field | Description |
|-------|-------------|
| `exDividendDate` | Ex-dividend date |
| `ROE` | Return on Equity |
| `annualGrowthRatio` | Annual growth ratio |
| `intrinsicValue` | Calculated intrinsic value |
| `discountToIntrinsicValueRatio` | Discount to intrinsic value |
| `targetRatio` | Target ratio |
| `dividendFrequency` | How often dividends are paid |
| `pegRatio` | PEG ratio |
| `peToGrowth` | P/E to growth ratio |

### ETFs

*(to be defined)*

### Currencies (Forex)

Forex pairs use the format `{CODE}{BASE}=X` (e.g. `EURUSD=X`, `JPYUSD=X`).
The `GET /symbol/{symbol}` endpoint returns OHLCV history; the `Close` field is used as the exchange rate.

**Response format:**

```json
{
  "symbol": "EURUSD=X",
  "history": {
    "2025-06-05 00:00:00+01:00": {
      "Open": 1.1422, "High": 1.1494, "Low": 1.1406,
      "Close": 1.1422, "Volume": 0
    }
  }
}
```text

| Endpoint | Used by |
|----------|---------|
| `GET /symbol/{code}{base}=X` | `POST /api/v1/currencies/sync` |

> The sync endpoint dynamically generates all unique currency pair combinations
> from the codes present in the database (format: `{CODE}{BASE}=X`), fetches
> OHLCV history from the Market API for each pair, and upserts `Close` values
> into the `currencies` table.

**Sync response format:**

```json
{
  "synced": true,
  "pairs": [
    {"code": "EUR", "base_code": "JPY", "rates_added": 260},
    {"code": "EUR", "base_code": "USD", "rates_added": 0, "error": "Market API error: ..."},
    {"code": "JPY", "base_code": "USD", "rates_added": 260}
  ],
  "total_rates": 520,
  "warning": "Market API error for EURUSD=X: ..."
}
```text

### Commodities

*(to be defined)*

## Implementation Requirements

- HTTP client wrapper for all endpoints
- Response caching (prices change less frequently than fundamentals)
- Error handling for API unavailability
- Rate limiting consideration

## Resilience (retry + circuit breaker + graceful fallback)

The external API is out of our control: it can be slow, return transient 5xx /
429, or be entirely unreachable. Resilience is enforced **inside
`MarketAPIClient._request()`** (new `services/api_resilience.py`), so callers
(`routes/market.py`, `currency_svc.sync_rates`, `health.py`) keep their public
interfaces unchanged. On a confirmed outage the app keeps serving with the last
known good data — see the stale-data signal below.

### Retry — exponential backoff with jitter

Applied per request through `httpx` transport retry hooks:

| Condition | Retried? |
|---|---|
| `ConnectError`, `TimeoutException` | ✅ |
| HTTP `5xx` | ✅ |
| HTTP `429` | ✅ (honors `Retry-After` when present) |
| Other `4xx` (incl. `404`) | ❌ fails fast (`MarketAPINotFound` stays authoritative) |

Defaults: `retry_attempts=3`, base delay `0.5s`, max delay `10s`, ±20% jitter.

### Circuit breaker — per `base_url`, in-process, thread-safe

```

closed → open → half-open → closed

```

- **Closed**: normal requests. `circuit_failure_threshold` (default 5)
  consecutive failures → **open**.
- **Open**: every request fails fast with `MarketAPIUnavailable` — no 30s
  timeout stall, no retry. Lasts `circuit_cooldown_seconds` (default 60).
- **Half-open**: one trial request after the cooldown. Success → **closed**;
  failure → **open** again.

The breaker is shared across request threads and the scheduler, so a confirmed
outage is detected once and all callers fail fast together.

### Fail-fast loops

`POST /market/sync-prices` and `POST /currencies/sync` check circuit state
before fanning out. When open they return immediately with
`circuit_open: true` and per-item `skipped` entries instead of burning
`N × timeout` seconds on a dead API. The existing per-pair/per-symbol error
shape is preserved for partial failures.

### Health integration

`/api/v1/health` reports the circuit state (`closed`/`open`/`half-open`) and
`last_success_at` under `checks.market_api`-adjacent fields. The health check
must not force additional attempts against an open circuit (a healthy-but-slow
API must not slow health).

### Stale-data signal (graceful fallback to the UI)

Analytics already degrade when prices are missing:
`latest prices row → latest INVESTMENT_BUY unit_price → none` (and manual
`tracking_mode`). What is missing is **telling the user** which fallback was
used and how old the price is. Holdings responses gain per-line price metadata
on `HoldingLine`:

- `price_source`: `market-api` | `transaction-fallback` | `manual` | `none`
- `price_as_of`: ISO timestamp of the price data (or null)

The portfolio/asset pages render a callout in the same style as the income /
cash-flow rate warning (`income.exchangeRateNote` — "Exchange rates from
{date}"): e.g. *"Prices from {date} — market data unavailable"* when any
holding is `transaction-fallback`, and *"No price data"* for `none`. i18n keys
added to EN/ES. This is the same mechanism as the income-page forex
extrapolation signal, applied to asset valuation.

### Config (`backend/config.json` → `market_api.*`)

| Key | Default | Meaning |
|---|---|---|
| `retry_attempts` | `3` | Max attempts per request (transient failures only) |
| `retry_base_delay` | `0.5` | Initial backoff seconds |
| `retry_max_delay` | `10` | Backoff ceiling in seconds |
| `circuit_failure_threshold` | `5` | Consecutive failures to trip the breaker |
| `circuit_cooldown_seconds` | `60` | Open-circuit hold time before half-open |
| `sync_cron_hours` | `[0, 12]` | UTC hours the scheduled full price sync fires |
| `sync_cron_pace_seconds` | `5` | Pause between symbol requests during the cron (full) sync |
| `sync_interactive_pace_seconds` | `2` | Pause between symbol requests during on-demand/auto syncs |
| `sync_freshness_hours` | `1` | Skip symbols whose last successful fetch is newer than this (interactive syncs only) |

Defaults are safe for dev; prod can tighten or loosen per observed API behavior.

## Price sync strategy

The bulk endpoint `POST /market/sync-prices` fans out over every auto-tracked
asset's `market_code` and calls `GET /symbol/{code}` per code. To avoid the
provider's throttling (which returns HTTP 500 when several symbols are requested
back-to-back), syncs are **paced** (a fixed sleep between symbols) and **avoid
redundant work** (freshness skip). There are three triggers, all sharing the
same code path via query parameters:

| Trigger | Params | Behaviour |
|---|---|---|
| **Scheduled cron** (00:00, 12:00 UTC) | `full=true, pace=5` | Full refresh — fetches every auto-tracked symbol, 5s apart. |
| **Manual "Sync Prices" button** | `full=false, pace=2, max_age_hours=1` | Incremental — skips symbols fetched < 1h ago. |
| **Auto-sync on `/market-assets` page open** | `full=false, pace=2, max_age_hours=1` | Same as the button; fire-and-forget. |

Common rules:

- `tracking_mode = manual` assets are always skipped (they have no market price).
- `last_synced_at` (per `market_assets` row) is updated **only on success**, so
  failed symbols are retried on the next run.
- **Single-flight**: an in-process guard ensures only one sync runs at a time;
  the scheduler job uses `max_instances=1` + coalesce, so cron and interactive
  syncs never overlap into a double burst.
- The circuit breaker remains the fail-fast for a confirmed outage.

## Implementation Status

- **Implemented**: `MarketAPIClient` class in `services/api_client.py`
- **Endpoints**: `/api/v1/market/health`, `/api/v1/market/{symbol}`, `/api/v1/market/{symbol}/price`, `/api/v1/market/{symbol}/{field}`
- **Currency sync**: `POST /api/v1/currencies/sync` — dynamically generates all currency pair combinations and upserts OHLCV close values
- **Tests**: Unit tests in `tests/test_market_api_client.py`
- **Required by**: Analytics Engine, Portfolio Valuation, Currency Sync
