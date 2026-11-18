"""Backfill ``cash_handling`` on legacy INVESTMENT_BUY rows.

Before the explicit funding modes a buy stored ``NULL`` and the engine resolved
it at record time. The intent is recoverable from what actually happened:

- funding pair + inferred-cash adjustment -> ``inject_pocket_main``
- funding pair, no injection              -> ``debit_pocket_main``
- no pair, inferred-cash adjustment       -> ``inject``
- no pair, no injection                   -> ``debit``

The old engine used the pocket first and injected only the shortfall, which is
exactly ``inject``; rows injected for their full amount simply had an empty
pocket and behave the same.

Idempotent: ``verify`` asserts no INVESTMENT_BUY is left with ``NULL``.
"""

from db.connection import _table_exists

BACKFILL_SQL = """
UPDATE transactions
SET cash_handling = CASE
    WHEN EXISTS (
        SELECT 1 FROM transaction_funding_links l WHERE l.transaction_id = transactions.id
    ) AND EXISTS (
        SELECT 1
        FROM balance_adjustment_links al
        JOIN transactions adj ON adj.id = al.balance_adjustment_id
        WHERE al.linked_transaction_id = transactions.id
          AND adj.balance_snapshot_id IS NULL
    ) THEN 'inject_pocket_main'
    WHEN EXISTS (
        SELECT 1 FROM transaction_funding_links l WHERE l.transaction_id = transactions.id
    ) THEN 'debit_pocket_main'
    WHEN EXISTS (
        SELECT 1
        FROM balance_adjustment_links al
        JOIN transactions adj ON adj.id = al.balance_adjustment_id
        WHERE al.linked_transaction_id = transactions.id
          AND adj.balance_snapshot_id IS NULL
    ) THEN 'inject'
    ELSE 'debit'
END
WHERE type = 'INVESTMENT_BUY' AND cash_handling IS NULL
"""


def up(conn) -> None:
    if not _table_exists(conn, "transactions"):
        return
    if not _table_exists(conn, "balance_adjustment_links") or not _table_exists(conn, "transaction_funding_links"):
        return
    conn.execute(BACKFILL_SQL)
    conn.commit()


def verify(conn) -> bool:
    if not _table_exists(conn, "transactions"):
        return False
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE type = 'INVESTMENT_BUY' AND cash_handling IS NULL LIMIT 1"
    ).fetchone()
    return row is None
