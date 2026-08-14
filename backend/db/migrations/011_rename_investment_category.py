"""Rename transactions.transaction_category to investment_transaction_category.

The field is investment-only (NORMAL/DCA/REBALANCE). SQLite RENAME COLUMN
(3.25+) updates the column-level CHECK constraint reference automatically.
Idempotent: no-op on fresh DBs (schema.sql already uses the new name) and on
databases that already renamed the column.
"""

from db.connection import _column_exists


def up(conn):
    if _column_exists(conn, "transactions", "transaction_category") and not _column_exists(
        conn, "transactions", "investment_transaction_category"
    ):
        conn.execute("ALTER TABLE transactions RENAME COLUMN transaction_category TO investment_transaction_category")
        conn.commit()


def verify(conn):
    return _column_exists(conn, "transactions", "investment_transaction_category")
