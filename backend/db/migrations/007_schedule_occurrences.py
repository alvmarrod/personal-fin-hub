"""Create schedule_occurrences table and backfill existing records."""

from db.connection import _migrate_schedule_occurrences, _table_exists


def up(conn):
    _migrate_schedule_occurrences(conn)


def verify(conn):
    return _table_exists(conn, "schedule_occurrences")
