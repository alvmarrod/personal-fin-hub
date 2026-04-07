# Subsystem: External Market API Client

## Base URL
`http://<host>:5001`

## Endpoints

### Health & Monitoring

- **GET /health**: Health check for container orchestration
- **GET /cache/status**: Cache statistics and scheduler status

### Symbol Data

- **GET /symbol/<tag>**: Fetch all available data for a stock symbol
- **GET /symbol/<tag>/<field>/**: Fetch specific field's value as JSON
- **GET /symbol/<tag>/<field>/raw**: Fetch raw field value
- **GET /symbol/historic/candle/<tag>**: Historical OHLCV data as CSV (5m candles, up to 60 days)

**Examples:**
```bash
# Health check
curl http://localhost:5001/health

# Cache status
curl http://localhost:5001/cache/status

# Fetch specific field (ROE)
curl http://localhost:5001/symbol/AAPL/ROE/
# Response: {"ROE": 1.7432836360316066}

# Fetch raw field value
curl http://localhost:5001/symbol/AAPL/ROE/raw
# Response: 1.7432836360316066

# Historical candles
curl http://localhost:5001/symbol/historic/candle/AAPL/raw
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

### Currencies
*(to be defined)*

### Commodities
*(to be defined)*

## Implementation Requirements

- HTTP client wrapper for all endpoints
- Response caching (prices change less frequently than fundamentals)
- Error handling for API unavailability
- Rate limiting consideration

## Implementation Status

- **Not implemented**: No API client code exists
- **Required by**: Analytics Engine, Portfolio Valuation