"""Create manual_values table."""

SQL = """
CREATE TABLE IF NOT EXISTS manual_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_asset_id INTEGER NOT NULL REFERENCES portfolio_assets(id),
    value REAL NOT NULL,
    effective_date DATE NOT NULL,
    recorded_at DATETIME NOT NULL DEFAULT (datetime('now')),
    notes TEXT,
    UNIQUE(portfolio_asset_id, effective_date)
);
"""


def up(conn):
    conn.executescript(SQL)
