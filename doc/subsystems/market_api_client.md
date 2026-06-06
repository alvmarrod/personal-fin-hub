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
```

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
```

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
```

### Commodities
*(to be defined)*

## Implementation Requirements

- HTTP client wrapper for all endpoints
- Response caching (prices change less frequently than fundamentals)
- Error handling for API unavailability
- Rate limiting consideration

## Implementation Status

- **Implemented**: `MarketAPIClient` class in `services/api_client.py`
- **Endpoints**: `/api/v1/market/health`, `/api/v1/market/{symbol}`, `/api/v1/market/{symbol}/price`, `/api/v1/market/{symbol}/{field}`
- **Currency sync**: `POST /api/v1/currencies/sync` — dynamically generates all currency pair combinations and upserts OHLCV close values
- **Tests**: Unit tests in `tests/test_market_api_client.py`
- **Required by**: Analytics Engine, Portfolio Valuation, Currency Sync