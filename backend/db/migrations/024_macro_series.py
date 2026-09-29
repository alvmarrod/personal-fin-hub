"""Create the macro source tables and seed the Wired series (Phase 1).

Two tables:

  - ``macro_series`` — one row per provider series (the registry). Keyed by a
    stable ``slug`` derived from the ``doc/kpis/world.md`` §2 sourcing tag, so
    the KPI layer can join on it without depending on the provider's URL id.
  - ``macro_series_observations`` — the raw ``(obs_date, value)`` time series, in
    the units the provider reports. ``UNIQUE(slug, obs_date)`` makes re-fetching
    idempotent.

Seeds the eight ``Wired`` rows in ``doc/datasources/macro.md`` (seven
Investing.com, one ECB). The ``Reserved`` Spain CPI row is deliberately not
seeded — the doc marks it not wired in.

Idempotent by presence: the tables are created with ``IF NOT EXISTS`` and each
series row is inserted only when its slug is absent, so a series a user added
by hand is left untouched. ``verify`` asserts presence-by-key, not value
equality.
"""

from db.connection import _table_exists

# (slug, provider, name, unit, source_url, update_frequency)
_SERIES = [
    (
        "boj-policy-rate",
        "investing-com",
        "Japan Interest Rate Decision",
        "%",
        "https://www.investing.com/economic-calendar/boj-interest-rate-decision-165",
        "event-driven",
    ),
    (
        "ecb-deposit-rate",
        "investing-com",
        "Eurozone Interest Rate Decision",
        "%",
        "https://www.investing.com/economic-calendar/interest-rate-decision-164",
        "event-driven",
    ),
    (
        "usa-cpi-yoy",
        "investing-com",
        "U.S. Consumer Price Index (CPI) YoY",
        "%",
        "https://www.investing.com/economic-calendar/cpi-733",
        "monthly",
    ),
    (
        "japan-cpi-yoy",
        "investing-com",
        "Japan National Consumer Price Index (CPI) YoY",
        "%",
        "https://www.investing.com/economic-calendar/japan-national-consumer-price-index-(cpi)-yoy-992",
        "monthly",
    ),
    (
        "eurozone-cpi-yoy",
        "investing-com",
        "Eurozone Consumer Price Index (CPI) YoY",
        "%",
        "https://www.investing.com/economic-calendar/cpi-68",
        "monthly",
    ),
    (
        "usa-m2-money-supply",
        "investing-com",
        "U.S. M2 Money Supply",
        None,
        "https://www.investing.com/economic-calendar/us-m2-money-supply-1999",
        "monthly",
    ),
    (
        "japan-m2-yoy",
        "investing-com",
        "Japan M2 Money Stock YoY",
        "%",
        "https://www.investing.com/economic-calendar/m2-money-stock-366",
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
        provider TEXT NOT NULL CHECK (provider IN ('investing-com', 'ecb')),
        name TEXT NOT NULL,
        unit TEXT,
        source_url TEXT NOT NULL,
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
