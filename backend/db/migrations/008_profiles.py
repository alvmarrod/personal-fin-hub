"""Add multi-profile support: profiles table + profile_id on ownership tables."""

from db.connection import PROFILE_TABLES, _column_exists, _migrate_profiles, _table_exists


def up(conn):
    _migrate_profiles(conn)


def verify(conn):
    if not _table_exists(conn, "profiles"):
        return False
    for table in PROFILE_TABLES:
        if _table_exists(conn, table) and not _column_exists(conn, table, "profile_id"):
            return False
    return conn.execute("SELECT 1 FROM profiles LIMIT 1").fetchone() is not None
