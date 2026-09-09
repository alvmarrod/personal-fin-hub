"""Backfill: convert existing JST wall-clock timestamps to UTC instants.

All existing timestamps in the DB are JST wall-clock times stored as naive
strings (or with a `+00:00` offset that was stripped on write).  This
migration converts them to UTC instants by subtracting 9 hours.

Affected tables:
  - transactions.timestamp (user-meaningful: JST → UTC)
  - balance_snapshots.timestamp (user-meaningful: JST → UTC)
  - manual_values.recorded_at (user-meaningful: JST → UTC)

System-time tables (prices, currencies) are untouched — they are already UTC.

IMPORTANT: This migration must run AFTER 019_add_profile_timezone so the
timezone column exists.  It uses the profile's timezone (default Asia/Tokyo)
to perform the conversion.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _parse_dt(s: str | None) -> datetime | None:
    """Parse a DATETIME string, handling both naive and aware formats."""
    if not s:
        return None
    # Strip offset suffix if present (e.g. '+00:00')
    clean = s.replace("+00:00", "").replace("Z", "").strip()
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return None


def _jst_to_utc_naive(dt: datetime) -> str:
    """Treat a naive datetime as JST, convert to UTC, return naive UTC string."""
    jst_aware = dt.replace(tzinfo=JST)
    utc_dt = jst_aware.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S")


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def up(conn):
    if verify(conn):
        logger.info("Migration 020: already converted, skipping")
        return
    if not _column_exists(conn, "transactions", "timestamp"):
        logger.warning("Migration 020: transactions table missing, skipping")
        return

    # --- transactions ---
    rows = conn.execute("SELECT id, timestamp FROM transactions").fetchall()
    updated = 0
    for row in rows:
        dt = _parse_dt(row["timestamp"])
        if dt is None:
            continue
        new_ts = _jst_to_utc_naive(dt)
        if new_ts != row["timestamp"]:
            conn.execute("UPDATE transactions SET timestamp = ? WHERE id = ?", (new_ts, row["id"]))
            updated += 1
    logger.info("Migration 020: transactions — %d rows converted", updated)

    # --- balance_snapshots ---
    if _column_exists(conn, "balance_snapshots", "timestamp"):
        rows = conn.execute("SELECT id, timestamp FROM balance_snapshots").fetchall()
        updated = 0
        for row in rows:
            dt = _parse_dt(row["timestamp"])
            if dt is None:
                continue
            new_ts = _jst_to_utc_naive(dt)
            if new_ts != row["timestamp"]:
                conn.execute("UPDATE balance_snapshots SET timestamp = ? WHERE id = ?", (new_ts, row["id"]))
                updated += 1
        logger.info("Migration 020: balance_snapshots — %d rows converted", updated)

    # --- manual_values ---
    if _column_exists(conn, "manual_values", "recorded_at"):
        rows = conn.execute("SELECT id, recorded_at FROM manual_values").fetchall()
        updated = 0
        for row in rows:
            dt = _parse_dt(row["recorded_at"])
            if dt is None:
                continue
            new_ts = _jst_to_utc_naive(dt)
            if new_ts != row["recorded_at"]:
                conn.execute("UPDATE manual_values SET recorded_at = ? WHERE id = ?", (new_ts, row["id"]))
                updated += 1
        logger.info("Migration 020: manual_values — %d rows converted", updated)

    conn.commit()
    logger.info("Migration 020: JST → UTC backfill complete")


def verify(conn):
    """Verify the JST → UTC backfill was applied.

    Correctly-converted data has no remaining offset suffixes (`+00:00`/`Z`)
    and no naive midnight (`T00:00:00`) timestamps — JST midnights all
    became `15:00:00` UTC the previous day.
    """
    if not _column_exists(conn, "transactions", "timestamp"):
        return True
    remaining_offsets = conn.execute(
        "SELECT COUNT(*) AS c FROM transactions WHERE timestamp LIKE '%+%' OR timestamp LIKE '%Z%'"
    ).fetchone()
    naive_midnights = conn.execute(
        "SELECT COUNT(*) AS c FROM transactions "
        "WHERE timestamp NOT LIKE '%+%' AND timestamp NOT LIKE '%Z%' "
        "AND timestamp LIKE '%T00:00:00'"
    ).fetchone()
    return remaining_offsets["c"] == 0 and naive_midnights["c"] == 0
