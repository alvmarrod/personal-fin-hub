"""Convert pre-timezone timestamps to UTC instants.

Before the timezone model, the app stored two timestamp populations:

  - User-entered values (transactions, balance snapshots, adjustment
    sentinels like ``T23:59:59``) were JST wall-clock times stored as
    naive strings.
  - Schedule materializations from the running in-app scheduler were
    stored as aware UTC strings (``datetime.now(UTC).isoformat()``,
    e.g. ``2026-08-01T05:30:00.123456+00:00``).

This migration normalizes both populations to naive UTC strings:

  - A value with an explicit offset (``+hh:mm`` or ``Z``) is already an
    instant: keep it and strip the offset.
  - A naive value is JST wall-clock: subtract 9 hours.

Affected tables:
  - transactions.timestamp
  - balance_snapshots.timestamp

System-time tables (prices, currencies) are untouched — they are already
UTC.  manual_values.recorded_at defaults to SQLite ``datetime('now')``
(UTC), is never written by code and is not shown in the UI, so it is
left alone.

IMPORTANT: This migration must run AFTER 019_add_profile_timezone.  The
interpretation zone is the profile's timezone (default Asia/Tokyo).
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _normalize_timestamp(value: str | None) -> str | None:
    """Normalize one stored timestamp to a naive UTC string.

    - Explicit offset (``+hh:mm``/``Z``) → already an instant; strip the offset.
    - Naive → JST wall-clock; convert to UTC.

    Returns None if the value cannot be parsed (the caller leaves it unchanged).
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    else:
        dt = dt.replace(tzinfo=JST).astimezone(UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _column_exists(conn, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _convert_column(conn, table: str, column: str) -> None:
    rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
    updated = 0
    for row in rows:
        normalized = _normalize_timestamp(row[column])
        if normalized is None or normalized == row[column]:
            continue
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (normalized, row["id"]))
        updated += 1
    logger.info("Migration 020: %s.%s — %d rows normalized", table, column, updated)


def up(conn):
    # The recorded marker, not verify(), decides whether to skip here: an
    # un-recorded database must be converted even when it carries no
    # offset-suffixed rows (e.g. a pre-model DB whose scheduler never fired).
    recorded = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", ("020_backfill_jst_to_utc",)
    ).fetchone()
    if recorded and verify(conn):
        logger.info("Migration 020: already normalized, skipping")
        return
    if not _column_exists(conn, "transactions", "timestamp"):
        logger.warning("Migration 020: transactions table missing, skipping")
        return

    _convert_column(conn, "transactions", "timestamp")
    if _column_exists(conn, "balance_snapshots", "timestamp"):
        _convert_column(conn, "balance_snapshots", "timestamp")

    conn.commit()
    logger.info("Migration 020: JST → UTC normalization complete")


def verify(conn):
    """No explicitly-offset timestamp may remain in the converted tables.

    A naive value is ambiguous as a conversion signal (a legit UTC instant
    can end in ``T00:00:00``), so the offset-suffix check is the only
    reliable \"was this normalized\" indicator.  Converted data written by
    the timezone-aware app never carries a suffix, so already-normalized
    databases pass and are skipped.
    """
    for table in ("transactions", "balance_snapshots"):
        if not _column_exists(conn, table, "timestamp"):
            continue
        remaining = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE timestamp LIKE '%+%' OR timestamp LIKE '%Z%'"
        ).fetchone()
        if remaining["c"] > 0:
            return False
    return True
