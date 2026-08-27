"""Add transactions.balance_snapshot_id FK; link and re-place existing adjustments."""

from datetime import datetime as _dt
from datetime import timedelta as _td


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _table_exists(conn, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def up(conn):
    if not _column_exists(conn, "transactions", "balance_snapshot_id"):
        conn.execute("ALTER TABLE transactions ADD COLUMN balance_snapshot_id INTEGER REFERENCES balance_snapshots(id)")

    if not _table_exists(conn, "balance_snapshots"):
        conn.commit()
        return

    # Link existing reconciliation adjustments to their snapshot. Old convention:
    # the adjustment sat at snapshot.date 00:00:00 (same timestamp as the snapshot).
    snapshots = conn.execute("SELECT id, entity_id, currency, timestamp FROM balance_snapshots").fetchall()
    for s in snapshots:
        old_ts = s["timestamp"][:10] + "T00:00:00"
        adj = conn.execute(
            "SELECT id FROM transactions "
            "WHERE entity_id = ? AND currency = ? AND type = 'BALANCE_ADJUSTMENT' AND timestamp = ? "
            "AND balance_snapshot_id IS NULL",
            (s["entity_id"], s["currency"], old_ts),
        ).fetchone()
        if adj:
            conn.execute("UPDATE transactions SET balance_snapshot_id = ? WHERE id = ?", (s["id"], adj["id"]))

    # Re-place linked adjustments at N-1 23:59:59 (strictly before the snapshot).
    linked = conn.execute(
        "SELECT id, balance_snapshot_id FROM transactions WHERE balance_snapshot_id IS NOT NULL"
    ).fetchall()
    snap_map = {r["id"]: r["timestamp"] for r in conn.execute("SELECT id, timestamp FROM balance_snapshots").fetchall()}
    for r in linked:
        ts = snap_map.get(r["balance_snapshot_id"])
        if not ts:
            continue
        d = _dt.strptime(ts[:10], "%Y-%m-%d")
        new_ts = (d - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"
        conn.execute("UPDATE transactions SET timestamp = ? WHERE id = ?", (new_ts, r["id"]))

    conn.commit()


def verify(conn):
    return _column_exists(conn, "transactions", "balance_snapshot_id")
