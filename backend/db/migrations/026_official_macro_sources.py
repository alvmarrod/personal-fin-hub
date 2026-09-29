"""Repoint the five Investing.com macro series to official sources.

Provider change (per doc/datasources/macro.md):

  - boj-policy-rate      -> Bank of Japan (IR01, daily, change points)
  - usa-cpi-yoy          -> BLS (CUUR0000SA0, monthly NSA, YoY derived)
  - eurozone-cpi-yoy     -> Eurostat (prc_hicp_manr, monthly annual rate)
  - usa-m2-money-supply  -> FRED (M2SL, monthly SA level)
  - japan-m2-yoy         -> Bank of Japan (MD02, monthly level, YoY derived)

Schema change: the ``provider`` CHECK now allows ``ecb``/``boj``/``bls``/
``eurostat``/``fred`` and no longer allows ``investing-com``. Because SQLite
cannot alter a CHECK in place, ``macro_series`` is rebuilt. ``provider`` and
``source_url`` become nullable so a series can exist with no datasource.

``japan-cpi-yoy`` has no official source yet, so it is left with a NULL
provider/source_url (it will be provided later). The observation rows are
preserved by the rebuild.

Idempotent: the rebuild only runs while the old CHECK is present, and the
data updates are repeated-safe. ``verify`` asserts the new CHECK and the final
per-slug provider/source_url.
"""

from db.connection import _table_exists

_OLD_CHECK_MARKER = "'investing-com'"

_NEW_TABLE_DDL = """
    CREATE TABLE macro_series_new (
        slug TEXT PRIMARY KEY,
        provider TEXT CHECK (provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred')),
        name TEXT NOT NULL,
        unit TEXT,
        source_url TEXT,
        update_frequency TEXT,
        last_synced_at DATETIME
    )
"""

# (slug, provider, name, source_url)
_REPOINT = [
    (
        "boj-policy-rate",
        "boj",
        "Japan Interest Rate Decision (Basic Discount Rate)",
        "https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=IR01&code=MADR1Z%40D",
    ),
    (
        "usa-cpi-yoy",
        "bls",
        "U.S. Consumer Price Index (CPI-U, All items, YoY)",
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
    ),
    (
        "eurozone-cpi-yoy",
        "eurostat",
        "HICP - monthly data (annual rate of change), Euro area, All-items",
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        "prc_hicp_manr?format=JSON&geo=EA&coicop=CP00&unit=RCH_A",
    ),
    (
        "usa-m2-money-supply",
        "fred",
        "M2 Money Stock (M2SL)",
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL",
    ),
    (
        "japan-m2-yoy",
        "boj",
        "Japan M2 Money Stock (YoY)",
        "https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=MD02&code=MAM1NAM2M2MO",
    ),
]

# Series with no official source yet: provider and source_url are cleared.
_UNSOURCED = ["japan-cpi-yoy"]


def _needs_rebuild(conn) -> bool:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='macro_series'").fetchone()
    return row is not None and _OLD_CHECK_MARKER in (row["sql"] or "")


def up(conn):
    if not _table_exists(conn, "macro_series"):
        return

    if _needs_rebuild(conn):
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute(_NEW_TABLE_DDL)
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(macro_series)").fetchall()]
            # The old rows may hold 'investing-com', which the new CHECK
            # rejects; map any non-allowed provider to NULL during the copy
            # (the UPDATEs below set the final values).
            select_cols = ", ".join(
                "CASE WHEN provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred') "
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

    for slug, provider, name, source_url in _REPOINT:
        conn.execute(
            "UPDATE macro_series SET provider = ?, name = ?, source_url = ? WHERE slug = ?",
            (provider, name, source_url, slug),
        )
    for slug in _UNSOURCED:
        conn.execute(
            "UPDATE macro_series SET provider = NULL, source_url = NULL WHERE slug = ?",
            (slug,),
        )
    conn.commit()


def verify(conn):
    if not _table_exists(conn, "macro_series"):
        return False
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='macro_series'").fetchone()
    sql = row["sql"] or "" if row else ""
    if _OLD_CHECK_MARKER in sql:
        return False
    if "'boj'" not in sql or "'fred'" not in sql:
        return False

    for slug, provider, _name, source_url in _REPOINT:
        found = conn.execute(
            "SELECT provider, source_url FROM macro_series WHERE slug = ?",
            (slug,),
        ).fetchone()
        if found is None or found["provider"] != provider or found["source_url"] != source_url:
            return False
    for slug in _UNSOURCED:
        found = conn.execute("SELECT provider, source_url FROM macro_series WHERE slug = ?", (slug,)).fetchone()
        if found is None or found["provider"] is not None or found["source_url"] is not None:
            return False
    return True
