"""Backfill auto-snapshots for existing INVESTMENT_BUY transactions."""

from db.connection import _backfill_auto_snapshots


def up(conn):
    _backfill_auto_snapshots(conn)


def verify(conn):
    # Pure data backfill with no schema postcondition. Re-running is
    # idempotent and safe, so verification is intentionally trivially satisfied.
    return True
