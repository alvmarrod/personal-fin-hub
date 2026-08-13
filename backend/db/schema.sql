CREATE TABLE currencies (
    code TEXT NOT NULL,
    base_code TEXT NOT NULL,
    rate REAL NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (code, base_code, timestamp)
);

CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('BROKER', 'BANK', 'EMPLOYER', 'EXCHANGE', 'OTHER')),
    country TEXT,
    description TEXT,
    deleted_at DATETIME DEFAULT NULL,
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_entities_profile ON entities(profile_id);

CREATE TABLE fiscal_exemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exemption_type TEXT NOT NULL,
    description TEXT,
    exemption_amount REAL DEFAULT 0,
    exemption_rate REAL DEFAULT 100,
    exemption_rate_limit REAL,
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_fiscal_exemptions_profile ON fiscal_exemptions(profile_id);

CREATE TABLE market_assets (
    market_code TEXT PRIMARY KEY,
    ticker TEXT,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('STOCK', 'ETF', 'ETC', 'FUND', 'INDEX FUND', 'CURRENCY', 'CRYPTO', 'OTHER')),
    asset_class TEXT CHECK (asset_class IN ('FI', 'VI', 'corp FI', 'Sovereign FI', 'mix FI', 'REIT', 'Gold', 'Monetary')),
    currency_code TEXT REFERENCES currencies(code),
    name TEXT,
    description TEXT,
    exchange TEXT,
    last_synced_at DATETIME
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
    notes TEXT,
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_assets_profile ON portfolio_assets(profile_id);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('MONEY_IN', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'DIVIDEND', 'INTEREST', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT')),
    transaction_category TEXT CHECK (transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
    income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest')),
    entity_id INTEGER NOT NULL REFERENCES entities(id),
    portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
    quantity REAL,
    unit_price REAL,
    currency TEXT NOT NULL REFERENCES currencies(code),
    total_value REAL,
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
    dividend_fx_rate REAL,
    notes TEXT,
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id);

CREATE TABLE transaction_fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    fee_type TEXT NOT NULL CHECK (fee_type IN ('BROKER', 'FX', 'PLATFORM', 'OTHER')),
    nature TEXT NOT NULL CHECK (nature IN ('FIXED', 'PERCENTAGE', 'BOTH', 'MIN')),
    fixed_amount REAL DEFAULT 0.0,
    percentage REAL DEFAULT 0.0,
    currency TEXT NOT NULL REFERENCES currencies(code),
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_transaction_fees_profile ON transaction_fees(profile_id);

CREATE TABLE transaction_taxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    tax_type TEXT NOT NULL,
    tax_rate REAL,
    tax_amount REAL,
    currency TEXT NOT NULL REFERENCES currencies(code),
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_transaction_taxes_profile ON transaction_taxes(profile_id);

CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL REFERENCES market_assets(market_code),
    timestamp DATETIME NOT NULL,
    price REAL NOT NULL,
    provider TEXT,
    UNIQUE(market_code, timestamp)
);

CREATE TABLE balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES entities(id),
    currency TEXT NOT NULL REFERENCES currencies(code),
    amount REAL NOT NULL,
    timestamp DATETIME NOT NULL,
    notes TEXT,
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_balance_snapshots_profile ON balance_snapshots(profile_id);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    periodicity_type TEXT NOT NULL CHECK (periodicity_type IN ('ONE_OFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY', 'CUSTOM')),
    custom_cron TEXT,
    linked_transaction_id INTEGER REFERENCES transactions(id),
    entity_id INTEGER REFERENCES entities(id),
    currency TEXT REFERENCES currencies(code),
    type TEXT,
    income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest')),
    total_value REAL,
    notes TEXT,
    portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
    profile_id INTEGER REFERENCES profiles(id)
);
CREATE INDEX IF NOT EXISTS idx_schedules_profile ON schedules(profile_id);

CREATE TABLE scheduler_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE schedule_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    occurrence_date TEXT NOT NULL,
    transaction_id INTEGER NOT NULL,
    profile_id INTEGER REFERENCES profiles(id),
    FOREIGN KEY (schedule_id) REFERENCES schedules(id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_occurrence ON schedule_occurrences(schedule_id, occurrence_date);
CREATE INDEX IF NOT EXISTS idx_schedule_occurrences_profile ON schedule_occurrences(profile_id);

CREATE TABLE stock_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL,
    split_date TEXT NOT NULL,
    ratio INTEGER NOT NULL CHECK (ratio >= 2),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (market_code) REFERENCES market_assets(market_code)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_split_year ON stock_splits(market_code, substr(split_date, 1, 4));

CREATE TABLE manual_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_asset_id INTEGER NOT NULL REFERENCES portfolio_assets(id),
    value REAL NOT NULL,
    effective_date DATE NOT NULL,
    recorded_at DATETIME NOT NULL DEFAULT (datetime('now')),
    notes TEXT,
    profile_id INTEGER REFERENCES profiles(id),
    UNIQUE(portfolio_asset_id, effective_date)
);
CREATE INDEX IF NOT EXISTS idx_manual_values_profile ON manual_values(profile_id);

CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);