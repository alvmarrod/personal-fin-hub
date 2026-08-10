"""Create manual_values table."""

from db.connection import _table_exists

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


def verify(conn):
    return _table_exists(conn, "manual_values")
