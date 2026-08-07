"""Backfill auto-snapshots for existing INVESTMENT_BUY transactions."""

from db.connection import _backfill_auto_snapshots


def up(conn):
    _backfill_auto_snapshots(conn)
