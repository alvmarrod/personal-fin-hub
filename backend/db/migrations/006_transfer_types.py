"""Widen transactions.type CHECK to accept TRANSFER_IN/TRANSFER_OUT."""

from db.connection import _migrate_transactions_check


def up(conn):
    _migrate_transactions_check(conn)
