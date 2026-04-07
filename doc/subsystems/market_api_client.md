# Subsystem: External Market API Client

## Specification Source
`README.md`

## Base URL
`http://<host>:<port>`

## Endpoints

### GET /symbol/<tag>
Fetch all available data for a symbol (company info, key stats, balance sheet, cash flow, earnings, analyst estimates).

### GET /symbol/<tag>/<field>/
Fetch specific field's value as JSON.

**Example:**
```bash
curl http://localhost:5000/symbol/AAPL/ROE/
```
```json
{"ROE": 1.7432836360316066}
```

### GET /symbol/<tag>/<field>/raw
Fetch specific field's raw value.

**Example:**
```bash
curl http://localhost:5000/symbol/AAPL/ROE/raw
```
```text
1.7432836360316066
```

### GET /symbol/historic/candle/<tag>
Download historical OHLCV data as CSV (5m candles, up to 60 days).

**Example:**
```bash
curl http://localhost:5000/symbol/historic/candle/AAPL/raw
```
```csv
Price,Close,High,Low,Open,Volume
Ticker,AAPL,AAPL,AAPL,AAPL,AAPL
Datetime,,,,,
2025-06-20 13:30:00+00:00,199.41079711914062,199.6300048828125,197.52999877929688,198.23500061035156,14021766
...
```

## Available Data Categories

### Corporate Info
Name, address, industry, sector, website, employees, executives

### Market Data
Price, range, volume, market cap, beta

### Financial Ratios
P/E, forward P/E, P/B, margins, ROE, ROA, growth rates

### Balance Sheet
Assets, liabilities, debt, equity, working capital

### P&L & Cash Flow
Revenue, EBITDA, net income, free cash flow, buybacks, debt issuance/repayment

### Analyst Estimates
Target price (high/low/mean), rating trends, recommendation summary

## Implementation Requirements
- HTTP client wrapper for all endpoints
- Response caching (prices change less frequently than fundamentals)
- Error handling for API unavailability
- Rate limiting consideration

## Implementation Status
- **Not implemented**: No API client code exists
- **Required by**: Analytics Engine, Portfolio Valuation