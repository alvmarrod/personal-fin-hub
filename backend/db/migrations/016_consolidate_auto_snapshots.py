"""Consolidate auto-snapshots into injected BALANCE_ADJUSTMENT transactions and
re-derive every manual snapshot's reconciliation adjustment (Phase 3).

The production database accumulated auto-generated cash snapshots (``Auto-*``
notes) at various points in time, against incomplete transaction sets, producing
stale, duplicated, and out-of-order entries. This migration deletes all of them
and rebuilds the inferred cash as signed ``BALANCE_ADJUSTMENT`` transactions
(``balance_snapshot_id = NULL``), computed minimally — just enough so each spend
never drives the pair negative, anchored on the surviving manual snapshots — and
then re-derives each manual snapshot's own adjustment (``balance_snapshot_id =
snapshot.id``) at ``N-1 23:59:59`` to reconcile the remaining difference.
"""

from collections import defaultdict
from datetime import datetime as _dt
from datetime import timedelta as _td

_SIGN = {
    "INCOME": 1.0,
    "INVESTMENT_SELL": 1.0,
    "TRANSFER_IN": 1.0,
    "MONEY_OUT": -1.0,
    "INVESTMENT_BUY": -1.0,
    "TRANSFER_OUT": -1.0,
}
_DECREASE = ("MONEY_OUT", "INVESTMENT_BUY", "TRANSFER_OUT")


def _day_before_235959(ts: str) -> str:
    d = _dt.strptime(ts[:10], "%Y-%m-%d")
    return (d - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"


def _reconcile_pair(conn, eid: int, cur: str) -> None:
    manual = conn.execute(
        "SELECT id, amount, timestamp, profile_id FROM balance_snapshots "
        "WHERE entity_id = ? AND currency = ? AND (notes IS NULL OR notes NOT LIKE 'Auto-%') "
        "ORDER BY timestamp, id",
        (eid, cur),
    ).fetchall()

    profile_id = None
    if manual:
        profile_id = manual[0]["profile_id"]
    else:
        row = conn.execute(
            "SELECT profile_id FROM transactions WHERE entity_id = ? AND currency = ? LIMIT 1", (eid, cur)
        ).fetchone()
        profile_id = row["profile_id"] if row else None

    txns = conn.execute(
        "SELECT id, type, total_value, timestamp FROM transactions "
        "WHERE entity_id = ? AND currency = ? AND type != 'BALANCE_ADJUSTMENT' "
        "ORDER BY timestamp, id",
        (eid, cur),
    ).fetchall()

    conn.execute(
        "DELETE FROM balance_snapshots WHERE entity_id = ? AND currency = ? AND notes LIKE 'Auto-%'", (eid, cur)
    )
    conn.execute(
        "DELETE FROM transactions WHERE entity_id = ? AND currency = ? AND type = 'BALANCE_ADJUSTMENT'", (eid, cur)
    )

    bal = 0.0
    injections: dict[str, float] = defaultdict(float)
    adjustments: list[tuple[int, float, str]] = []
    mi = 0
    for tx in txns:
        t = tx["type"]
        v = tx["total_value"] or 0.0
        while mi < len(manual) and manual[mi]["timestamp"] <= tx["timestamp"]:
            s = manual[mi]
            adjustments.append((s["id"], s["amount"] - bal, s["timestamp"]))
            bal = s["amount"]
            mi += 1
        if t in _DECREASE and bal < v:
            injections[_day_before_235959(tx["timestamp"])] += v - bal
            bal = v
        bal += _SIGN.get(t, 0.0) * v

    while mi < len(manual):
        s = manual[mi]
        adjustments.append((s["id"], s["amount"] - bal, s["timestamp"]))
        bal = s["amount"]
        mi += 1

    for date, amount in injections.items():
        conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, balance_snapshot_id, notes, profile_id) "
            "VALUES (?, 'BALANCE_ADJUSTMENT', ?, ?, ?, NULL, ?, ?)",
            (date, eid, cur, amount, "Inferred cash for investment purchases", profile_id),
        )

    for sid, amount, ts in adjustments:
        conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, balance_snapshot_id, notes, profile_id) "
            "VALUES (?, 'BALANCE_ADJUSTMENT', ?, ?, ?, ?, ?, ?)",
            (_day_before_235959(ts), eid, cur, amount, sid, f"Balance adjustment for snapshot at {ts}", profile_id),
        )


def _table_exists(conn, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def up(conn):
    if not _table_exists(conn, "balance_snapshots"):
        conn.commit()
        return
    pairs = conn.execute("SELECT DISTINCT entity_id, currency FROM balance_snapshots").fetchall()
    for p in pairs:
        _reconcile_pair(conn, p["entity_id"], p["currency"])
    conn.commit()


def verify(conn):
    if not _table_exists(conn, "balance_snapshots"):
        return True
    row = conn.execute("SELECT COUNT(*) AS c FROM balance_snapshots WHERE notes LIKE 'Auto-%'").fetchone()
    return row["c"] == 0
