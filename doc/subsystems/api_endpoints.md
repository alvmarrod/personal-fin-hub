# Subsystem: API Endpoints

## Resources Overview

| Resource | Endpoints | Notes |
|----------|-----------|-------|
| **Market Assets** | GET, POST, PUT, DELETE `/market-assets` | Market data from external API |
| **Portfolio Assets** | GET, POST, PUT, DELETE `/portfolio-assets` | User portfolio positions |
| **Transactions** | GET, POST, PUT, DELETE `/transactions` | Core resource |
| **Transaction Fees** | GET, POST, PUT, DELETE `/transaction-fees` | 1:N with transactions |
| **Transaction Taxes** | GET, POST, PUT, DELETE `/transaction-taxes` | 1:N with transactions (including withholding) |
| **Entities** | GET, POST, PUT, DELETE `/entities` | Brokers, exchanges, counterparties |
| **Fiscal Exemptions** | GET, POST, PUT, DELETE `/fiscal-exemptions` | Tax exemption types |
| **Currencies** | GET, POST, PUT, DELETE `/currencies` | ISO codes or custom |
| **Prices** | GET, POST, PUT, DELETE `/prices` | Daily/timestamped market prices |
| **Schedules** | GET, POST, PUT, DELETE `/schedules` | Recurring transactions |

## Transactional Endpoints

### 1. Create Full Transaction
`POST /transactions/full`

Creates transaction with fees and taxes atomically.

**Payload:**
```json
{
  "transaction": {
    "portfolio_asset_id": 1,
    "quantity": 10,
    "unit_price": 100.5,
    "currency": "USD",
    "timestamp": "2025-09-17T09:00:00Z",
    "type": "INVESTMENT_BUY",
    "payment_currency": "JPY",
    "fx_rate": 150.5
  },
  "fees": [
    {
      "fee_type": "BROKER",
      "nature": "PERCENTAGE",
      "fixed_amount": 0,
      "percentage": 0.05,
      "currency": "USD"
    }
  ],
  "taxes": [
    {
      "tax_type": "STAMP_DUTY",
      "tax_rate": 0.1,
      "tax_amount": 1.0,
      "currency": "USD"
    }
  ]
}
```

### 2. Create Dividend Transaction
`POST /transactions/full`

Withholding taxes linked to dividend transaction.

**Payload:**
```json
{
  "transaction": {
    "portfolio_asset_id": 1,
    "quantity": 100,
    "unit_price": 0.25,
    "currency": "USD",
    "timestamp": "2025-09-17T09:00:00Z",
    "type": "DIVIDEND",
    "dividend_type": "regular",
    "record_date": "2025-09-01",
    "payment_date": "2025-09-15",
    "gross_amount": 25.00,
    "dividend_currency": "USD",
    "dividend_payment_currency": "JPY",
    "dividend_fx_rate": 150.5
  },
  "taxes": [
    {
      "tax_type": "WITHHOLDING",
      "tax_rate": 15,
      "tax_amount": 3.75,
      "currency": "USD"
    }
  ]
}
```

### 3. Transfer Between Entities
`POST /transfers`

**Payload:**
```json
{
  "from_entity_id": 1,
  "to_entity_id": 2,
  "amount": 1000,
  "currency": "EUR",
  "timestamp": "2025-09-17T10:00:00Z",
  "fees": [...]
}
```

### 4. Batch Import
`POST /transactions/batch`

Creates multiple transactions atomically. All succeed or all roll back.

**Payload:**
```json
{
  "transactions": [
    {
      "timestamp": "2025-09-17T10:00:00Z",
      "type": "MONEY_IN",
      "entity_id": 1,
      "currency": "EUR",
      "total_value": 1000.0
    },
    {
      "timestamp": "2025-09-17T10:00:00Z",
      "type": "INVESTMENT_BUY",
      "entity_id": 1,
      "portfolio_asset_id": 5,
      "currency": "EUR",
      "quantity": 10,
      "unit_price": 50.0
    }
  ]
}
```

**Response (201):**
```json
{
  "transactions": [
    { "id": 101, "total_value": 1000.0, ... },
    { "id": 102, "total_value": 500.0, ... }
  ]
}
```

### 5. Schedule with Initial Transaction
`POST /schedules/full`

Creates a schedule linked to its initial transaction atomically. The transaction is created first, then the schedule points to it via `linked_transaction_id`. When the APScheduler runtime fires, it clones this initial transaction.

**Payload:**
```json
{
  "schedule": {
    "description": "Monthly DCA",
    "start_date": "2025-01-01",
    "periodicity_type": "MONTHLY"
  },
  "transaction": {
    "timestamp": "2025-09-17T10:00:00Z",
    "type": "INVESTMENT_BUY",
    "entity_id": 1,
    "currency": "USD",
    "quantity": 10.0,
    "unit_price": 50.0
  }
}
```

**Response (201):**
```json
{
  "schedule": {
    "id": 1,
    "description": "Monthly DCA",
    "start_date": "2025-01-01",
    "periodicity_type": "MONTHLY",
    "linked_transaction_id": 101
  },
  "transaction": {
    "id": 101,
    "total_value": 500.0,
    "type": "INVESTMENT_BUY",
    ...
  }
}
```

## Models

### MarketAsset
```json
{
  "market_code": "string",
  "ticker": "string | null",
  "asset_type": "enum [STOCK, ETF, ETC, FUND, INDEX FUND, CURRENCY, CRYPTO, OTHER]",
  "asset_class": "enum [FI, VI, corp FI, Sovereign FI, mix FI, REIT, Gold, Monetary] | null",
  "currency_code": "string",
  "name": "string",
  "description": "string | null",
  "exchange": "string | null"
}
```

### PortfolioAsset
```json
{
  "id": "integer",
  "market_code": "string",
  "distribution_type": "enum [accumulation, distribution, N/A] | null",
  "dca_status": "enum [ongoing, paused, closed] | null",
  "layer": "enum [core, reserve, satellite] | null",
  "tactic": "boolean",
  "desired_weight": "decimal | null",
  "ter": "decimal | null",
  "tracking_mode": "enum [auto, manual]",
  "current_value_manual": "decimal | null",
  "is_active": "boolean",
  "closing_date": "date | null",
  "purchase_date": "date | null",
  "notes": "string | null"
}
```

### Transaction
```json
{
  "id": "integer",
  "portfolio_asset_id": "integer | null",
  "entity_id": "integer",
  "timestamp": "datetime",
  "type": "enum [MONEY_IN, MONEY_OUT, INVESTMENT_BUY, INVESTMENT_SELL, DIVIDEND, INTEREST, TRANSFER]",
  "transaction_category": "enum [NORMAL, DCA, REBALANCE] | null",
  "quantity": "decimal | null",
  "unit_price": "decimal | null",
  "currency": "string",
  "total_value": "decimal",
  "gross_amount": "decimal | null",
  "net_amount": "decimal | null",
  "payment_currency": "string | null",
  "fx_rate": "decimal | null",
  "settlement_date": "date | null",
  "fiscal_exemption_id": "integer | null",
  "dividend_type": "enum [regular, special, qualified] | null",
  "record_date": "date | null",
  "payment_date": "date | null",
  "dividend_currency": "string | null",
  "dividend_payment_currency": "string | null",
  "dividend_fx_rate": "decimal | null",
  "notes": "string | null"
}
```

### TransactionFee
```json
{
  "id": "integer",
  "transaction_id": "integer",
  "fee_type": "enum [BROKER, FX, PLATFORM, OTHER]",
  "nature": "enum [FIXED, PERCENTAGE, BOTH, MIN]",
  "fixed_amount": "decimal",
  "percentage": "decimal",
  "currency": "string"
}
```

### TransactionTax
```json
{
  "id": "integer",
  "transaction_id": "integer",
  "tax_type": "string (e.g., WITHHOLDING, STAMP_DUTY, VAT, CAPITAL_GAINS)",
  "tax_rate": "decimal | null",
  "tax_amount": "decimal",
  "currency": "string"
}
```

### Entity
```json
{
  "id": "integer",
  "name": "string",
  "entity_type": "enum [BROKER, BANK, EMPLOYER, EXCHANGE, OTHER]",
  "country": "string | null",
  "description": "string | null"
}
```

### FiscalExemption
```json
{
  "id": "integer",
  "exemption_type": "string (e.g., NISA, ISA, 401k, Pension)",
  "description": "string | null",
  "exemption_amount": "decimal",
  "exemption_rate": "decimal (100 = 100%)",
  "exemption_rate_limit": "decimal | null"
}
```

### Schedule
```json
{
  "id": "integer",
  "description": "string",
  "start_date": "date",
  "end_date": "date | null",
  "periodicity_type": "enum [ONE_OFF, DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY, CUSTOM]",
  "custom_cron": "string | null",
  "linked_transaction_id": "integer | null"
}
```

## Implementation Status
- **All CRUD endpoints** under `/api/v1` (entities, currencies, market_assets, portfolio_assets, fiscal_exemptions, transactions, transaction_fees, transaction_taxes, prices, schedules) — **implemented**
- **Composite endpoints:**
  - `POST /transactions/full` — implemented (7 tests)
  - `POST /transfers` — implemented (15 tests)
  - `POST /transactions/batch` — implemented (7 tests)
  - `POST /schedules/full` — implemented (6 tests)
- **Scheduler (APScheduler):** implemented (18 tests) — background job runner at app startup, auto-sync on schedule CRUD, clones linked transactions with fees/taxes

### Analytics Endpoints
- `GET /analytics/dashboard` — Dashboard summary
- `GET /analytics/holdings` — Holdings with P&L
- `GET /analytics/allocation?dimension=layer|asset_type|currency|asset_class|entity` — Allocation grouped by dimension
- `GET /analytics/cash-flow?group_by=&start_date=&end_date=` — Cash flow analysis
- `GET /analytics/dividends?start_date=&end_date=` — Dividend income
- `GET /analytics/fees-taxes?start_date=&end_date=` — Fee and tax totals
- `GET /analytics/performance` — Performance summary
- `GET /analytics/realized-gains` — Per-asset realized gains
- `GET /analytics/historical?start_date=&end_date=&interval=` — Historical portfolio value
- `GET /analytics/holdings-by-entity` — Cross-tabulation entity × asset_class

All analytics endpoints implemented and tested (94 tests).