"""Effective-dated investment strategy targets.

One set is the five bucket rows that share an ``effective_from`` date. The
target for a date is the newest set that started on or before it.

Idempotent: ``verify`` checks the table and the unique key.
"""

from db.connection import _table_exists

TABLE_DDL = """
    CREATE TABLE IF NOT EXISTS strategy_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        effective_from DATE NOT NULL,
        bucket TEXT NOT NULL,
        target_pct REAL NOT NULL CHECK (target_pct >= 0 AND target_pct <= 100),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (profile_id, effective_from, bucket)
    )
"""


def up(conn):
    if not _table_exists(conn, "strategy_targets"):
        conn.execute(TABLE_DDL)
        conn.commit()


def verify(conn):
    if not _table_exists(conn, "strategy_targets"):
        return False
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(strategy_targets)").fetchall()}
    return {"profile_id", "effective_from", "bucket", "target_pct"} <= columns
