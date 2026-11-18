"""Add the FX_CONVERSION type, ``auto_generated`` and the cash-flow view.

A currency conversion is a single transaction: ``currency`` (source) is
debited by ``total_value`` and ``payment_currency`` (destination) is credited
by ``gross_amount``. ``auto_generated`` separates conversions the funding
engine creates from user-recorded broker conversions.

``transaction_cash_flows`` normalizes every transaction into signed per-pocket
movements so the cash queries can stay single-sided.

Idempotent: ``verify`` checks the type CHECK, the column and the view.
"""

from db.connection import _column_exists

TRANSACTIONS_DDL = """
    CREATE TABLE transactions_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT', 'FX_CONVERSION')),
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
        auto_generated INTEGER NOT NULL DEFAULT 0,
        profile_id INTEGER REFERENCES profiles(id)
    )
"""

VIEW_DDL = """
    CREATE VIEW transaction_cash_flows AS
    SELECT
        t.id AS transaction_id,
        t.profile_id,
        t.entity_id,
        t.timestamp,
        COALESCE(t.payment_currency, t.currency) AS currency,
        CASE
            WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN COALESCE(t.gross_amount, t.total_value)
            WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -COALESCE(t.gross_amount, t.total_value)
            WHEN t.type = 'BALANCE_ADJUSTMENT' THEN COALESCE(t.total_value, 0.0)
            ELSE 0
        END AS amount
    FROM transactions t
    WHERE t.type <> 'FX_CONVERSION'
    UNION ALL
    SELECT t.id, t.profile_id, t.entity_id, t.timestamp, t.currency, -COALESCE(t.total_value, 0.0)
    FROM transactions t
    WHERE t.type = 'FX_CONVERSION'
    UNION ALL
    SELECT t.id, t.profile_id, t.entity_id, t.timestamp, t.payment_currency,
           COALESCE(t.gross_amount, t.total_value * t.fx_rate)
    FROM transactions t
    WHERE t.type = 'FX_CONVERSION'
"""


def _transactions_sql(conn) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'transactions'").fetchone()
    return row["sql"] if row else ""


def _view_exists(conn) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'view' AND name = 'transaction_cash_flows'"
    ).fetchone()
    return row is not None


def verify(conn) -> bool:
    return (
        "FX_CONVERSION" in _transactions_sql(conn)
        and _column_exists(conn, "transactions", "auto_generated")
        and _view_exists(conn)
    )


def up(conn) -> None:
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP VIEW IF EXISTS transaction_cash_flows")
        conn.execute(TRANSACTIONS_DDL)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall())
        conn.execute(f"INSERT INTO transactions_new ({cols}) SELECT {cols} FROM transactions")
        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id)")
        conn.execute(VIEW_DDL)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={foreign_keys}")
