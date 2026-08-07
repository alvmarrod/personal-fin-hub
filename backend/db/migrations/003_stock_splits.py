"""Create stock_splits table."""

SQL = """
CREATE TABLE IF NOT EXISTS stock_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL,
    split_date TEXT NOT NULL,
    ratio INTEGER NOT NULL CHECK (ratio >= 2),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (market_code) REFERENCES market_assets(market_code)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_split_year ON stock_splits(market_code, substr(split_date, 1, 4));
"""


def up(conn):
    conn.executescript(SQL)
