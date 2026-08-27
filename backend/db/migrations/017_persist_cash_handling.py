"""Persist cash-handling decisions: ``transactions.cash_handling`` +
``balance_adjustment_links`` junction table (reconciliation persistence, Phase A).

- ``transactions.cash_handling`` stores the user's inject/debit choice for spend
  rows (``'inject'`` | ``'debit'``; ``NULL`` = smart default decided at record
  time). Historical rows are intentionally left ``NULL`` — no retroactive
  intent is fabricated.
- ``balance_adjustment_links`` attaches an injected ``BALANCE_ADJUSTMENT``
  (``balance_snapshot_id IS NULL``) to the same-day spends it funds, replacing
  the implicit "spends dated one day after the injection" convention with an
  explicit link. Anchors are mutually exclusive: snapshot-linked adjustments
  never appear here.
- Backfill links every existing injected adjustment (marker note) to ALL
  same-pair spends dated exactly one day later. Injections with no next-day
  spend stay unlinked (legitimate state, logged at verify time).
"""

import logging
from datetime import datetime as _dt
from datetime import timedelta as _td

logger = logging.getLogger(__name__)

_SPEND_TYPES = ("INVESTMENT_BUY", "MONEY_OUT", "TRANSFER_OUT")
_INJECTION_NOTE = "Inferred cash for investment purchases"

_LINKS_DDL = """
    CREATE TABLE IF NOT EXISTS balance_adjustment_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        balance_adjustment_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
        linked_transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
        UNIQUE(balance_adjustment_id, linked_transaction_id)
    )
"""


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _table_exists(conn, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _next_day(ts: str) -> str:
    d = _dt.strptime(ts[:10], "%Y-%m-%d")
    return (d + _td(days=1)).strftime("%Y-%m-%d")


def _backfill_links(conn) -> int:
    """Link existing standalone injections to their next-day spends."""
    placeholders = ", ".join("?" for _ in _SPEND_TYPES)
    injections = conn.execute(
        "SELECT id, entity_id, currency, timestamp FROM transactions "
        "WHERE type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id IS NULL AND notes = ?",
        (_INJECTION_NOTE,),
    ).fetchall()

    linked = 0
    for inj in injections:
        spend_date = _next_day(inj["timestamp"])
        spends = conn.execute(
            f"SELECT id FROM transactions "
            f"WHERE entity_id = ? AND currency = ? AND type IN ({placeholders}) "
            f"AND timestamp >= ? AND timestamp < ?",
            (
                inj["entity_id"],
                inj["currency"],
                *_SPEND_TYPES,
                spend_date + "T00:00:00",
                spend_date + "T23:59:59",
            ),
        ).fetchall()
        for sp in spends:
            cur = conn.execute(
                "INSERT OR IGNORE INTO balance_adjustment_links (balance_adjustment_id, linked_transaction_id) "
                "VALUES (?, ?)",
                (inj["id"], sp["id"]),
            )
            linked += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return linked


def up(conn):
    if not _column_exists(conn, "transactions", "cash_handling"):
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN cash_handling TEXT CHECK (cash_handling IN ('inject', 'debit'))"
        )

    created_table = not _table_exists(conn, "balance_adjustment_links")
    if created_table:
        conn.execute(_LINKS_DDL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_balance_adjustment_links_adj ON balance_adjustment_links(balance_adjustment_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_balance_adjustment_links_tx ON balance_adjustment_links(linked_transaction_id)"
        )

    inserted = _backfill_links(conn)
    conn.commit()
    if created_table or inserted:
        logger.info("Migration 017: balance_adjustment_links ready, %d link(s) backfilled", inserted)


def verify(conn):
    if not _column_exists(conn, "transactions", "cash_handling"):
        return False
    if not _table_exists(conn, "balance_adjustment_links"):
        return False

    unlinked = conn.execute(
        "SELECT COUNT(*) AS c FROM transactions t "
        "WHERE t.type = 'BALANCE_ADJUSTMENT' AND t.balance_snapshot_id IS NULL AND t.notes = ? "
        "AND NOT EXISTS (SELECT 1 FROM balance_adjustment_links l WHERE l.balance_adjustment_id = t.id)",
        (_INJECTION_NOTE,),
    ).fetchone()["c"]
    if unlinked:
        logger.info("Migration 017: %d injected adjustment(s) have no next-day spend and remain unlinked", unlinked)
    return True
