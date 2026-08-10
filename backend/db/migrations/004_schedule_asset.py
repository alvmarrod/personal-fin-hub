"""Add portfolio_asset_id column to schedules."""

from db.connection import _column_exists


def up(conn):
    cursor = conn.execute("PRAGMA table_info(schedules)")
    cols = [row["name"] for row in cursor.fetchall()]
    if "portfolio_asset_id" not in cols:
        conn.execute("ALTER TABLE schedules ADD COLUMN portfolio_asset_id INTEGER REFERENCES portfolio_assets(id)")


def verify(conn):
    return _column_exists(conn, "schedules", "portfolio_asset_id")
