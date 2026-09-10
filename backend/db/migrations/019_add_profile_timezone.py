"""Add ``profiles.timezone``: IANA timezone identifier for the profile.

All user-entered dates are interpreted in this zone; all stored UTC
timestamps are displayed in this zone.  Default ``Asia/Tokyo`` matches
the current user's timezone.  Existing rows inherit this default.
"""

import logging

logger = logging.getLogger(__name__)


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def up(conn):
    if not _column_exists(conn, "profiles", "timezone"):
        conn.execute("ALTER TABLE profiles ADD COLUMN timezone TEXT DEFAULT 'Asia/Tokyo'")
        conn.commit()
        logger.info("Migration 019: profiles.timezone added")


def verify(conn):
    return _column_exists(conn, "profiles", "timezone")
