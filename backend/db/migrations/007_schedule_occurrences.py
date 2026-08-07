"""Create schedule_occurrences table and backfill existing records."""

from db.connection import _migrate_schedule_occurrences


def up(conn):
    _migrate_schedule_occurrences(conn)
