"""Widen ``cash_handling`` and add the buy-funding link table.

``INVESTMENT_BUY`` gains two explicit funding modes that draw on the entity's
main-currency pocket (``debit_pocket_main``, ``inject_pocket_main``). SQLite
cannot alter a CHECK constraint in place, so the transactions table is rebuilt
without a ``cash_handling`` CHECK; the enum is validated by Pydantic instead.

The rebuild also creates ``transaction_funding_links``: the generated FX pair
that funds a buy is attached to it there (one row per leg).

Idempotent: ``verify`` checks the end-state (no ``cash_handling`` CHECK and the
links table present).
"""

from db.connection import _table_exists

TRANSACTIONS_DDL = """
    CREATE TABLE transactions_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT')),
        investment_transaction_category TEXT CHECK (investment_transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
        income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest', 'cashback')),
        entity_id INTEGER NOT NULL REFERENCES entities(id),
        portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
        quantity REAL,
        unit_price REAL,
        currency TEXT NOT NULL REFERENCES currencies(code),
        total_value REAL,
        gross_amount REAL,
        net_amount REAL,
        payment_currency TEXT REFERENCES currencies(code),
        fx_rate REAL,
        settlement_date DATE,
        fiscal_exemption_id INTEGER REFERENCES fiscal_exemptions(id),
        fiscal_rule TEXT,
        dividend_type TEXT CHECK (dividend_type IN ('regular', 'special', 'qualified')),
        record_date DATE,
        payment_date DATE,
        dividend_currency TEXT REFERENCES currencies(code),
        dividend_payment_currency TEXT REFERENCES currencies(code),
        dividend_fx_rate REAL,
        notes TEXT,
        balance_snapshot_id INTEGER REFERENCES balance_snapshots(id),
        cash_handling TEXT,
        profile_id INTEGER REFERENCES profiles(id)
    )
"""


def _transactions_sql(conn) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'transactions'").fetchone()
    return row["sql"] if row else ""


def verify(conn) -> bool:
    return "cash_handling IN" not in _transactions_sql(conn) and _table_exists(conn, "transaction_funding_links")


def up(conn) -> None:
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(TRANSACTIONS_DDL)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall())
        conn.execute(f"INSERT INTO transactions_new ({cols}) SELECT {cols} FROM transactions")
        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_funding_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
                funding_transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
                UNIQUE(transaction_id, funding_transaction_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transaction_funding_links_tx ON transaction_funding_links(transaction_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transaction_funding_links_funding "
            "ON transaction_funding_links(funding_transaction_id)"
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={foreign_keys}")
