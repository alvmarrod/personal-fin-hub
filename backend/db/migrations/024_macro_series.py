"""Create the macro source tables and seed the Wired series (Phase 1).

Two tables:

  - ``macro_series`` — one row per provider series (the registry). Keyed by a
    stable ``slug`` derived from the ``doc/kpis/world.md`` §2 sourcing tag, so
    the KPI layer can join on it without depending on the provider's URL id.
  - ``macro_series_observations`` — the raw ``(obs_date, value)`` time series, in
    the units the provider reports. ``UNIQUE(slug, obs_date)`` makes re-fetching
    idempotent.

Seeds the eight ``Wired`` rows in ``doc/datasources/macro.md`` (official
providers). The ``Reserved`` Spain CPI row is deliberately not
seeded — the doc marks it not wired in.

Idempotent by presence: the tables are created with ``IF NOT EXISTS`` and each
series row is inserted only when its slug is absent, so a series a user added
by hand is left untouched. ``verify`` asserts presence-by-key, not value
equality.
"""

from db.connection import _table_exists

# (slug, provider, name, unit, source_url, update_frequency)
# Provider/source values are the final official sources; later migrations
# (025 for the ECB deposit rate, 026 for the rest) repoint databases whose 024
# ran with the original Investing.com values.
_SERIES = [
    (
        "boj-policy-rate",
        "boj",
        "Japan Interest Rate Decision (Basic Discount Rate)",
        "%",
        "https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=IR01&code=MADR1Z%40D",
        "event-driven",
    ),
    (
        "ecb-deposit-rate",
        "ecb",
        "ECB Deposit Facility Rate (date of changes)",
        "%",
        "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=jsondata",
        "event-driven",
    ),
    (
        "usa-cpi-yoy",
        "bls",
        "U.S. Consumer Price Index (CPI-U, All items, YoY)",
        "%",
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "monthly",
    ),
    (
        "japan-cpi-yoy",
        None,
        "Japan National Consumer Price Index (CPI) YoY",
        "%",
        None,
        "monthly",
    ),
    (
        "eurozone-cpi-yoy",
        "eurostat",
        "HICP - monthly data (annual rate of change), Euro area, All-items",
        "%",
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        "prc_hicp_manr?format=JSON&geo=EA&coicop=CP00&unit=RCH_A",
        "monthly",
    ),
    (
        "usa-m2-money-supply",
        "fred",
        "M2 Money Stock (M2SL)",
        None,
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL",
        "monthly",
    ),
    (
        "japan-m2-yoy",
        "boj",
        "Japan M2 Money Stock (YoY)",
        "%",
        "https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=MD02&code=MAM1NAM2M2MO",
        "monthly",
    ),
    (
        "eurozone-m2-yoy",
        "ecb",
        "Eurozone M2 (annual growth rate)",
        "%",
        "https://data.ecb.europa.eu/data-detail-api/BSI.M.U2.Y.V.M20.X.I.U2.2300.Z01.A",
        "monthly",
    ),
]

_DDL_SERIES = """
    CREATE TABLE IF NOT EXISTS macro_series (
        slug TEXT PRIMARY KEY,
        provider TEXT CHECK (provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred')),
        name TEXT NOT NULL,
        unit TEXT,
        source_url TEXT,
        update_frequency TEXT,
        last_synced_at DATETIME
    )
"""

_DDL_OBSERVATIONS = """
    CREATE TABLE IF NOT EXISTS macro_series_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL REFERENCES macro_series(slug),
        obs_date DATE NOT NULL,
        value REAL NOT NULL,
        UNIQUE(slug, obs_date)
    )
"""


def up(conn):
    conn.execute(_DDL_SERIES)
    conn.execute(_DDL_OBSERVATIONS)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_macro_obs_slug ON macro_series_observations(slug)")

    for slug, provider, name, unit, source_url, update_frequency in _SERIES:
        conn.execute(
            "INSERT OR IGNORE INTO macro_series (slug, provider, name, unit, source_url, update_frequency) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (slug, provider, name, unit, source_url, update_frequency),
        )

    conn.commit()


def verify(conn):
    if not (_table_exists(conn, "macro_series") and _table_exists(conn, "macro_series_observations")):
        return False
    for slug, *_rest in _SERIES:
        if conn.execute("SELECT 1 FROM macro_series WHERE slug = ?", (slug,)).fetchone() is None:
            return False
    return True
