CREATE TABLE currencies (
    code TEXT NOT NULL,
    base_code TEXT NOT NULL,
    rate REAL NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (code, base_code, timestamp)
);

CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('BROKER', 'BANK', 'EMPLOYER', 'EXCHANGE', 'OTHER')),
    country TEXT,
    description TEXT
);

CREATE TABLE fiscal_exemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exemption_type TEXT NOT NULL,
    description TEXT,
    exemption_amount REAL DEFAULT 0,
    exemption_rate REAL DEFAULT 100,
    exemption_rate_limit REAL
);

CREATE TABLE market_assets (
    market_code TEXT PRIMARY KEY,
    ticker TEXT,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('STOCK', 'ETF', 'ETC', 'FUND', 'INDEX FUND', 'CURRENCY', 'CRYPTO', 'OTHER')),
    asset_class TEXT CHECK (asset_class IN ('FI', 'VI', 'corp FI', 'Sovereign FI', 'mix FI', 'REIT', 'Gold', 'Monetary')),
    currency_code TEXT REFERENCES currencies(code),
    name TEXT,
    description TEXT,
    exchange TEXT
);

CREATE TABLE portfolio_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL REFERENCES market_assets(market_code),
    distribution_type TEXT CHECK (distribution_type IN ('accumulation', 'distribution', 'N/A')),
    dca_status TEXT CHECK (dca_status IN ('ongoing', 'paused', 'closed')),
    layer TEXT CHECK (layer IN ('core', 'reserve', 'satellite')),
    tactic BOOLEAN DEFAULT FALSE,
    desired_weight REAL,
    ter REAL,
    tracking_mode TEXT CHECK (tracking_mode IN ('auto', 'manual')) DEFAULT 'auto',
    current_value_manual REAL,
    is_active BOOLEAN DEFAULT TRUE,
    closing_date DATE,
    purchase_date DATE,
    notes TEXT
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('MONEY_IN', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'DIVIDEND', 'INTEREST', 'TRANSFER')),
    transaction_category TEXT CHECK (transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
    entity_id INTEGER NOT NULL REFERENCES entities(id),
    portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
    quantity REAL,
    unit_price REAL,
    currency TEXT NOT NULL REFERENCES currencies(code),
    total_value REAL GENERATED ALWAYS AS (quantity * unit_price) STORED,
    gross_amount REAL,
    net_amount REAL,
    payment_currency TEXT REFERENCES currencies(code),
    fx_rate REAL,
    settlement_date DATE,
    fiscal_exemption_id INTEGER REFERENCES fiscal_exemptions(id),
    dividend_type TEXT CHECK (dividend_type IN ('regular', 'special', 'qualified')),
    record_date DATE,
    payment_date DATE,
    dividend_currency TEXT REFERENCES currencies(code),
    dividend_payment_currency TEXT REFERENCES currencies(code),
    dividend_fx_rate REAL
);

CREATE TABLE transaction_fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    fee_type TEXT NOT NULL CHECK (fee_type IN ('BROKER', 'FX', 'PLATFORM', 'OTHER')),
    nature TEXT NOT NULL CHECK (nature IN ('FIXED', 'PERCENTAGE', 'BOTH', 'MIN')),
    fixed_amount REAL DEFAULT 0.0,
    percentage REAL DEFAULT 0.0,
    currency TEXT NOT NULL REFERENCES currencies(code)
);

CREATE TABLE transaction_taxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    tax_type TEXT NOT NULL,
    tax_rate REAL,
    tax_amount REAL,
    currency TEXT NOT NULL REFERENCES currencies(code)
);

CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL REFERENCES market_assets(market_code),
    timestamp DATETIME NOT NULL,
    price REAL NOT NULL,
    provider TEXT
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    periodicity_type TEXT NOT NULL CHECK (periodicity_type IN ('ONE_OFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY', 'CUSTOM')),
    custom_cron TEXT,
    linked_transaction_id INTEGER REFERENCES transactions(id)
);