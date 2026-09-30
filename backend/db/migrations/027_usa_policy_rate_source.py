"""Add the USA policy-rate proxy series, sourced from the External Market API.

Seeds ``usa-13w-bill-rate`` — the 13-week Treasury bill yield (``^IRX``) served
by the External Market API — as the ``policy_rate`` USA world KPI (a proxy; see
``doc/kpis/world.md`` §2).

Schema change: the ``macro_series.provider`` CHECK gains ``market-api`` (the
datasource client that fetches a market symbol). The other providers are
unchanged. Because SQLite cannot alter a CHECK in place, ``macro_series`` is
rebuilt when the value is absent. Observations are preserved by the rebuild.

Idempotent: the rebuild only runs while ``market-api`` is not yet allowed, and
the seed uses ``INSERT OR IGNORE``. ``verify`` asserts the CHECK and the row.
"""

from db.connection import _table_exists

_NEW_CHECK_MARKER = "'market-api'"

_NEW_TABLE_DDL = """
    CREATE TABLE macro_series_new (
        slug TEXT PRIMARY KEY,
        provider TEXT CHECK (provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred', 'market-api')),
        name TEXT NOT NULL,
        unit TEXT,
        source_url TEXT,
        update_frequency TEXT,
        last_synced_at DATETIME
    )
"""

_SLUG = "usa-13w-bill-rate"
_SERIES = (
    _SLUG,
    "market-api",
    "US 13-week Treasury bill rate (policy-rate proxy)",
    "%",
    "^IRX",
    "daily",
)


def _needs_rebuild(conn) -> bool:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='macro_series'").fetchone()
    return row is not None and _NEW_CHECK_MARKER not in (row["sql"] or "")


def up(conn):
    if not _table_exists(conn, "macro_series"):
        return

    if _needs_rebuild(conn):
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute(_NEW_TABLE_DDL)
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(macro_series)").fetchall()]
            select_cols = ", ".join(
                "CASE WHEN provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred', 'market-api') "
                "THEN provider ELSE NULL END AS provider"
                if c == "provider"
                else c
                for c in cols
            )
            conn.execute(f"INSERT INTO macro_series_new ({', '.join(cols)}) SELECT {select_cols} FROM macro_series")
            conn.execute("DROP TABLE macro_series")
            conn.execute("ALTER TABLE macro_series_new RENAME TO macro_series")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(f"PRAGMA foreign_keys={foreign_keys}")

    conn.execute(
        "INSERT OR IGNORE INTO macro_series (slug, provider, name, unit, source_url, update_frequency) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        _SERIES,
    )
    conn.commit()


def verify(conn):
    if not _table_exists(conn, "macro_series"):
        return False
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='macro_series'").fetchone()
    if _NEW_CHECK_MARKER not in (row["sql"] or "" if row else ""):
        return False
    found = conn.execute("SELECT provider FROM macro_series WHERE slug = ?", (_SLUG,)).fetchone()
    return found is not None and found["provider"] == "market-api"
