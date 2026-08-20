"""Add tax_rates table and profiles.default_fiscal_rule.

Creates the ``tax_rates`` table for per-ruleset/category/year bracket
management and adds a nullable ``default_fiscal_rule`` column to ``profiles``
for per-profile default ruleset override. Seeds initial rates for spain,
japan, and default rulesets. Idempotent.
"""

from db.connection import _column_exists, _table_exists

_SEED_RATES = [
    # Spain progressive savings-income brackets (capital_gains + dividends share these bands)
    ("spain", "capital_gains", 0, 6000, 0.19, None),
    ("spain", "capital_gains", 6000, 50000, 0.21, None),
    ("spain", "capital_gains", 50000, None, 0.23, None),
    ("spain", "dividends", 0, 6000, 0.19, None),
    ("spain", "dividends", 6000, 50000, 0.21, None),
    ("spain", "dividends", 50000, None, 0.23, None),
    # Japan flat rates
    ("japan", "capital_gains", 0, None, 0.20315, None),
    ("japan", "dividends", 0, None, 0.20315, None),
    # Default = copy of Spain
    ("default", "capital_gains", 0, 6000, 0.19, None),
    ("default", "capital_gains", 6000, 50000, 0.21, None),
    ("default", "capital_gains", 50000, None, 0.23, None),
    ("default", "dividends", 0, 6000, 0.19, None),
    ("default", "dividends", 6000, 50000, 0.21, None),
    ("default", "dividends", 50000, None, 0.23, None),
]


def up(conn):
    if not _table_exists(conn, "tax_rates"):
        conn.execute(
            """
            CREATE TABLE tax_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ruleset_key TEXT NOT NULL,
                category TEXT NOT NULL CHECK (category IN ('capital_gains', 'dividends')),
                from_amount REAL NOT NULL DEFAULT 0,
                to_amount REAL,
                rate REAL NOT NULL,
                year_start INTEGER,
                profile_id INTEGER REFERENCES profiles(id)
            )
            """
        )
        conn.execute("CREATE INDEX idx_tax_rates_key ON tax_rates(ruleset_key, category, year_start)")
        for ruleset_key, category, from_amount, to_amount, rate, year_start in _SEED_RATES:
            conn.execute(
                "INSERT INTO tax_rates (ruleset_key, category, from_amount, to_amount, rate, year_start) VALUES (?, ?, ?, ?, ?, ?)",
                (ruleset_key, category, from_amount, to_amount, rate, year_start),
            )
    if not _column_exists(conn, "profiles", "default_fiscal_rule"):
        conn.execute("ALTER TABLE profiles ADD COLUMN default_fiscal_rule TEXT")
    conn.commit()


def verify(conn):
    return _table_exists(conn, "tax_rates") and _column_exists(conn, "profiles", "default_fiscal_rule")
