"""Add ``entities.supports_multi_currency``.

TRUE (1) = the entity can hold cash in several currencies; FALSE (0) = one
account currency, enforced from ``main_currency``. Existing rows are backfilled
to TRUE, which preserves the behaviour they had before the column existed.

Idempotent: ``verify`` checks the column exists.
"""

from db.connection import _column_exists


def up(conn):
    if not _column_exists(conn, "entities", "supports_multi_currency"):
        conn.execute("ALTER TABLE entities ADD COLUMN supports_multi_currency INTEGER NOT NULL DEFAULT 1")
        conn.commit()


def verify(conn):
    return _column_exists(conn, "entities", "supports_multi_currency")
