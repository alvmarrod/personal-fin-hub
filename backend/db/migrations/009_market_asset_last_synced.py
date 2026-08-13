"""Add market_assets.last_synced_at for price-sync freshness skip."""

from db.connection import _column_exists, _table_exists


def up(conn):
    if not _table_exists(conn, "market_assets"):
        return
    if not _column_exists(conn, "market_assets", "last_synced_at"):
        conn.execute("ALTER TABLE market_assets ADD COLUMN last_synced_at DATETIME")
        conn.commit()


def verify(conn):
    if not _table_exists(conn, "market_assets"):
        return True
    return _column_exists(conn, "market_assets", "last_synced_at")
