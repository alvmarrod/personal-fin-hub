"""Drop deprecated purchase_date column from portfolio_assets."""

from db.connection import _column_exists


def up(conn):
    cursor = conn.execute("PRAGMA table_info(portfolio_assets)")
    cols = [row["name"] for row in cursor.fetchall()]
    if "purchase_date" in cols:
        conn.execute("ALTER TABLE portfolio_assets DROP COLUMN purchase_date")


def verify(conn):
    return not _column_exists(conn, "portfolio_assets", "purchase_date")
