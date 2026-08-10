"""Widen transactions.type CHECK to accept TRANSFER_IN/TRANSFER_OUT."""

from db.connection import _migrate_transactions_check


def up(conn):
    _migrate_transactions_check(conn)


def verify(conn):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'").fetchone()
    return row is not None and "TRANSFER_IN" in row["sql"]
