"""Add income_category to schedules and transactions for explicit income classification."""

from db.connection import _column_exists


def up(conn):
    if not _column_exists(conn, "schedules", "income_category"):
        conn.execute("ALTER TABLE schedules ADD COLUMN income_category TEXT")
    if not _column_exists(conn, "transactions", "income_category"):
        conn.execute("ALTER TABLE transactions ADD COLUMN income_category TEXT")
    conn.commit()


def verify(conn):
    return _column_exists(conn, "schedules", "income_category") and _column_exists(
        conn, "transactions", "income_category"
    )
