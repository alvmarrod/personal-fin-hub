"""Add multi-profile support: profiles table + profile_id on ownership tables."""

from db.connection import _migrate_profiles


def up(conn):
    _migrate_profiles(conn)
