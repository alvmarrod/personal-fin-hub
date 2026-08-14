"""Add fiscal_periods and transactions.fiscal_rule for rule snapshotting.

Creates the profile-scoped ``fiscal_periods`` table (rule assignment over a
date range) and adds a nullable ``fiscal_rule`` column to ``transactions`` so
each INVESTMENT_SELL snapshots the rule active on its date. Idempotent: no-op on
fresh DBs (schema.sql already defines both) and on DBs that already migrated.
"""

from db.connection import _column_exists, _table_exists


def up(conn):
    if not _table_exists(conn, "fiscal_periods"):
        conn.execute(
            """
            CREATE TABLE fiscal_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER REFERENCES profiles(id),
                rule_key TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE
            )
            """
        )
        conn.execute("CREATE INDEX idx_fiscal_periods_profile ON fiscal_periods(profile_id)")
    if not _column_exists(conn, "transactions", "fiscal_rule"):
        conn.execute("ALTER TABLE transactions ADD COLUMN fiscal_rule TEXT")
    conn.commit()


def verify(conn):
    return _table_exists(conn, "fiscal_periods") and _column_exists(conn, "transactions", "fiscal_rule")
