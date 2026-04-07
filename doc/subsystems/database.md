# Subsystem: Database

## Schema Source
`backend/db/schema.sql`

## Tables

### market_assets
| Column | Type | Constraints |
|--------|------|-------------|
| `market_code` | TEXT | PRIMARY KEY |
| `ticker` | TEXT | Exchange-specific (e.g., "AAPL.US", "TEF.MC") |
| `asset_type` | TEXT | NOT NULL, CHECK (STOCK, ETF, ETC, FUND, INDEX FUND, CURRENCY, CRYPTO, OTHER) |
| `asset_class` | TEXT | CHECK (FI, VI, corp FI, Sovereign FI, mix FI, REIT, Gold, Monetary) |
| `currency_code` | TEXT | REFERENCES currencies(code) |
| `name` | TEXT | |
| `description` | TEXT | |
| `exchange` | TEXT | |

### portfolio_assets
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `market_code` | TEXT | NOT NULL, REFERENCES market_assets(market_code) |
| `distribution_type` | TEXT | CHECK (accumulation, distribution, N/A) |
| `dca_status` | TEXT | CHECK (ongoing, paused, closed) |
| `layer` | TEXT | CHECK (core, reserve, satellite) |
| `tactic` | BOOLEAN | DEFAULT FALSE |
| `desired_weight` | REAL | Target weight 0-100% |
| `ter` | REAL | Total Expense Ratio (e.g., 0.5 = 0.5%) |
| `is_active` | BOOLEAN | DEFAULT TRUE |
| `closing_date` | DATE | |
| `purchase_date` | DATE | |
| `notes` | TEXT | |

### transactions
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `timestamp` | DATETIME | NOT NULL |
| `type` | TEXT | NOT NULL, CHECK (MONEY_IN, MONEY_OUT, INVESTMENT_BUY, INVESTMENT_SELL, DIVIDEND, INTEREST, TRANSFER) |
| `transaction_category` | TEXT | CHECK (NORMAL, DCA, REBALANCE) |
| `entity_id` | INTEGER | NOT NULL, REFERENCES entities(id) |
| `portfolio_asset_id` | INTEGER | REFERENCES portfolio_assets(id) |
| `quantity` | REAL | |
| `unit_price` | REAL | |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |
| `total_value` | REAL | GENERATED (quantity * unit_price) |
| `gross_amount` | REAL | Before fees and tax |
| `net_amount` | REAL | After fees and tax |
| `payment_currency` | TEXT | REFERENCES currencies(code) |
| `fx_rate` | REAL | 1 currency = X payment_currency |
| `settlement_date` | DATE | |
| `fiscal_exemption_id` | INTEGER | References fiscal_exemptions(id) |
| `dividend_type` | TEXT | CHECK (regular, special, qualified) |
| `record_date` | DATE | Dividend eligibility date |
| `payment_date` | DATE | Dividend payment date |
| `dividend_currency` | TEXT | Original dividend currency |
| `dividend_payment_currency` | TEXT | Currency received |
| `dividend_fx_rate` | REAL | 1 dividend_currency = X payment_currency |

### transaction_fees
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `transaction_id` | INTEGER | NOT NULL, REFERENCES transactions(id) |
| `fee_type` | TEXT | NOT NULL, CHECK (BROKER, FX, PLATFORM, OTHER) |
| `nature` | TEXT | NOT NULL, CHECK (FIXED, PERCENTAGE, BOTH, MIN) |
| `fixed_amount` | REAL | DEFAULT 0.0 |
| `percentage` | REAL | DEFAULT 0.0 |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |

### transaction_taxes
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `transaction_id` | INTEGER | NOT NULL, REFERENCES transactions(id) |
| `tax_type` | TEXT | NOT NULL (e.g., WITHHOLDING, STAMP_DUTY, VAT, CAPITAL_GAINS) |
| `tax_rate` | REAL | |
| `tax_amount` | REAL | |
| `currency` | TEXT | NOT NULL, REFERENCES currencies(code) |

### schedules
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `description` | TEXT | NOT NULL |
| `start_date` | DATE | NOT NULL |
| `end_date` | DATE | |
| `periodicity_type` | TEXT | NOT NULL, CHECK (ONE_OFF, DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY, CUSTOM) |
| `custom_cron` | TEXT | |
| `linked_transaction_id` | INTEGER | REFERENCES transactions(id) |

### currencies
| Column | Type | Constraints |
|--------|------|-------------|
| `code` | TEXT | NOT NULL |
| `base_code` | TEXT | NOT NULL |
| `rate` | REAL | NOT NULL |
| `timestamp` | DATETIME | NOT NULL |
| PRIMARY KEY | (code, base_code, timestamp) |

### prices
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `market_code` | TEXT | NOT NULL, REFERENCES market_assets(market_code) |
| `timestamp` | DATETIME | NOT NULL |
| `price` | REAL | NOT NULL |
| `provider` | TEXT | |

### entities
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `entity_type` | TEXT | NOT NULL, CHECK (BROKER, BANK, EMPLOYER, EXCHANGE, OTHER) |
| `country` | TEXT | |
| `description` | TEXT | |

### fiscal_exemptions
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `exemption_type` | TEXT | NOT NULL (e.g., NISA, ISA, 401k) |
| `description` | TEXT | |
| `exemption_amount` | REAL | DEFAULT 0 |
| `exemption_rate` | REAL | DEFAULT 100 (100%) |
| `exemption_rate_limit` | REAL | NULL = no limit |

## Relationships
- portfolio_assets (many) → market_assets (one)
- transactions (many) → portfolio_assets (one) via portfolio_asset_id
- transactions (many) → entities (one)
- transactions (many) → fiscal_exemptions (one)
- transaction_fees (many) → transactions (one)
- transaction_taxes (many) → transactions (one)
- prices (many) → market_assets (one)

## Design Notes
- Denormalized schema optimized for analytics
- Dividend withholding taxes are modeled via transaction_taxes with tax_type=WITHHOLDING, linked to DIVIDEND transactions
- portfolio_assets.is_active can be derived from transactions but denormalized for performance