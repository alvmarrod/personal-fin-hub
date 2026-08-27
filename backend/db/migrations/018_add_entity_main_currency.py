"""Add ``entities.main_currency``: the entity's main cash pocket.

Fee and tax rows are cash-outs charged to this pair. When the fee/tax is
recorded in another currency the amount is converted at the parent
transaction's timestamp (nearest stored rate). ``NULL`` (default for all
existing rows) falls back to charging the fee's own recorded
``(entity_id, currency)`` pair without conversion.
"""

import logging

logger = logging.getLogger(__name__)


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def up(conn):
    if not _column_exists(conn, "entities", "main_currency"):
        conn.execute("ALTER TABLE entities ADD COLUMN main_currency TEXT REFERENCES currencies(code)")
        conn.commit()
        logger.info("Migration 018: entities.main_currency added")


def verify(conn):
    return _column_exists(conn, "entities", "main_currency")
