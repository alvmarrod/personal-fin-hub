"""Add the USA 10-year Treasury yield series for the yield-curve slope.

Seeds ``usa-10y-treasury-yield`` — the 10-year Treasury yield (``^TNX``) served
by the External Market API — as the ``yield_10y`` world KPI (USA). Together with
``usa-13w-bill-rate`` (``^IRX``) it lets the derived layer compute
``yield_curve_slope`` = ``^TNX − ^IRX`` per ``doc/derived/macro.md``.

Data-only migration: no schema change (``market-api`` is already an allowed
provider). Idempotent: ``INSERT OR IGNORE``; ``verify`` asserts the row.
"""

from db.connection import _table_exists

_SLUG = "usa-10y-treasury-yield"
_SERIES = (
    _SLUG,
    "market-api",
    "US 10-year Treasury yield",
    "%",
    "^TNX",
    "daily",
)


def up(conn):
    if not _table_exists(conn, "macro_series"):
        return
    conn.execute(
        "INSERT OR IGNORE INTO macro_series (slug, provider, name, unit, source_url, update_frequency) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _SERIES,
    )
    conn.commit()


def verify(conn):
    if not _table_exists(conn, "macro_series"):
        return False
    row = conn.execute("SELECT provider FROM macro_series WHERE slug = ?", (_SLUG,)).fetchone()
    return row is not None and row["provider"] == "market-api"
