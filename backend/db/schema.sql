
CREATE TABLE assets (
    asset_code TEXT PRIMARY KEY,         -- e.g.: "AAPL", "GLD", "USDJPY=X"
    asset_type TEXT NOT NULL CHECK (asset_type IN ('STOCK', 'ETF', 'CURRENCY', 'COMMODITY', 'CRYPTO', 'OTHER')),
    description TEXT,
    currency_code TEXT NOT NULL REFERENCES currencies(code)
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('MONEY_IN', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER')),
    entity_id INTEGER NOT NULL REFERENCES entities(id),
    asset_code TEXT REFERENCES assets(asset_code), -- NULL if classifies as cash-in/cash-out
    quantity REAL,                                 -- e.g.: asset amount
    unit_price REAL,                               -- Unit price at the given currency
    currency TEXT NOT NULL REFERENCES currencies(code),
    total_value REAL GENERATED ALWAYS AS (quantity * unit_price) STORED
);

CREATE TABLE transaction_fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    fee_type TEXT NOT NULL CHECK (fee_type IN ('BROKER', 'FX', 'PLATFORM', 'OTHER')),
    nature TEXT NOT NULL CHECK (nature IN ('FIXED', 'PERCENTAGE', 'BOTH', 'MIN')),
    fixed_amount REAL DEFAULT 0.0,
    percentage REAL DEFAULT 0.0,   -- e.g.: 0.5 means 0.5%
    currency TEXT NOT NULL REFERENCES currencies(code)
);

CREATE TABLE transaction_taxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    tax_type TEXT NOT NULL,      -- e.g.: WITHHOLDING, CAPITAL_GAINS
    tax_rate REAL,               -- % applied
    tax_amount REAL,             -- calculated tax amount
    currency TEXT NOT NULL REFERENCES currencies(code)
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    periodicity_type TEXT NOT NULL CHECK (periodicity_type IN ('ONE_OFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY', 'CUSTOM')),
    custom_cron TEXT, -- if periodicity_type='CUSTOM', save cron rule
    linked_transaction_id INTEGER REFERENCES transactions(id)
);

CREATE TABLE currencies (
    code TEXT NOT NULL,
    base_code TEXT NOT NULL,              -- Currency base for the rate
    rate REAL NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (code, base_code, timestamp)
);

CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL REFERENCES assets(asset_code),
    timestamp DATETIME NOT NULL,
    price REAL NOT NULL,
    provider TEXT
);

CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                     -- e.g.: "Interactive Brokers", "Nomura Bank"
    entity_type TEXT NOT NULL CHECK (entity_type IN ('BROKER', 'BANK', 'EMPLOYER', 'EXCHANGE', 'OTHER')),
    country TEXT,                           -- ISO-3166, e.g.: "JP"
    description TEXT
);
