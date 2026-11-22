"""Debt tracking: payable and receivable debt, rates, payments and plan.

Adds four profile-scoped tables, links one schedule to a debt, and widens the
``transactions.type`` CHECK with ``DEBT_IN`` / ``DEBT_OUT``. Those cash
movements are neither income nor expenses, so the cash-flow view carries their
signs explicitly.

Idempotent: ``verify`` checks the tables, the schedule link, the type CHECK and
the view.
"""

from db.connection import _column_exists, _table_exists

DEBTS_DDL = """
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        direction TEXT NOT NULL CHECK (direction IN ('payable', 'receivable')),
        counterparty_name TEXT NOT NULL,
        description TEXT,
        currency TEXT NOT NULL REFERENCES currencies(code),
        principal REAL NOT NULL CHECK (principal >= 0),
        start_date DATE NOT NULL,
        term_months INTEGER,
        maturity_date DATE,
        installment_mode TEXT NOT NULL CHECK (installment_mode IN ('equal_payment', 'equal_principal', 'interest_only', 'manual')),
        installment_amount REAL,
        principal_per_installment REAL,
        day_count TEXT NOT NULL CHECK (day_count IN ('monthly', 'actual_365', 'actual_360', 'thirty_360')),
        rate_reset_mode TEXT NOT NULL CHECK (rate_reset_mode IN ('recalculate_installment', 'keep_installment')),
        review_period_months INTEGER,
        disbursement_mode TEXT NOT NULL CHECK (disbursement_mode IN ('pocket', 'none')),
        disbursement_entity_id INTEGER REFERENCES entities(id),
        disbursement_date DATE,
        status TEXT NOT NULL CHECK (status IN ('active', 'settled', 'cancelled')),
        settled_at DATE,
        settled_amount REAL,
        settlement_adjustment REAL,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""

DEBT_RATES_DDL = """
    CREATE TABLE IF NOT EXISTS debt_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        debt_id INTEGER NOT NULL REFERENCES debts(id),
        effective_from DATE NOT NULL,
        annual_rate REAL NOT NULL CHECK (annual_rate >= 0 AND annual_rate <= 100),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (debt_id, effective_from)
    )
"""

DEBT_PLAN_ENTRIES_DDL = """
    CREATE TABLE IF NOT EXISTS debt_plan_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        debt_id INTEGER NOT NULL REFERENCES debts(id),
        period_no INTEGER NOT NULL,
        due_date DATE NOT NULL,
        payment_amount REAL NOT NULL,
        principal_amount REAL NOT NULL,
        interest_amount REAL NOT NULL,
        fees_amount REAL NOT NULL DEFAULT 0,
        insurance_amount REAL NOT NULL DEFAULT 0,
        other_amount REAL NOT NULL DEFAULT 0,
        imported_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (debt_id, due_date)
    )
"""

DEBT_PAYMENTS_DDL = """
    CREATE TABLE IF NOT EXISTS debt_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        debt_id INTEGER NOT NULL REFERENCES debts(id),
        paid_at DATE NOT NULL,
        amount REAL NOT NULL,
        principal_amount REAL NOT NULL DEFAULT 0,
        interest_amount REAL NOT NULL DEFAULT 0,
        fees_amount REAL NOT NULL DEFAULT 0,
        insurance_amount REAL NOT NULL DEFAULT 0,
        other_amount REAL NOT NULL DEFAULT 0,
        kind TEXT NOT NULL CHECK (kind IN ('regular', 'extra', 'settlement')),
        transaction_id INTEGER REFERENCES transactions(id),
        plan_entry_id INTEGER REFERENCES debt_plan_entries(id),
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_debts_profile ON debts(profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_debt_rates_profile ON debt_rates(profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_debt_rates_debt ON debt_rates(debt_id, effective_from)",
    "CREATE INDEX IF NOT EXISTS idx_debt_plan_entries_profile ON debt_plan_entries(profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_debt_plan_entries_debt ON debt_plan_entries(debt_id, due_date)",
    "CREATE INDEX IF NOT EXISTS idx_debt_payments_profile ON debt_payments(profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_debt_payments_debt ON debt_payments(debt_id, paid_at)",
    "CREATE INDEX IF NOT EXISTS idx_schedules_debt ON schedules(debt_id)",
]

TRANSACTIONS_DDL = """
    CREATE TABLE transactions_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT', 'FX_CONVERSION', 'DEBT_IN', 'DEBT_OUT')),
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
            WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN', 'DEBT_IN') THEN COALESCE(t.gross_amount, t.total_value)
            WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT', 'DEBT_OUT') THEN -COALESCE(t.gross_amount, t.total_value)
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


def _view_sql(conn) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'view' AND name = 'transaction_cash_flows'"
    ).fetchone()
    return row["sql"] if row else ""


def _rebuild_transactions(conn) -> None:
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
    finally:
        conn.execute(f"PRAGMA foreign_keys={foreign_keys}")


def up(conn) -> None:
    if not _table_exists(conn, "debts"):
        conn.execute(DEBTS_DDL)
    if not _table_exists(conn, "debt_rates"):
        conn.execute(DEBT_RATES_DDL)
    if not _table_exists(conn, "debt_plan_entries"):
        conn.execute(DEBT_PLAN_ENTRIES_DDL)
    if not _table_exists(conn, "debt_payments"):
        conn.execute(DEBT_PAYMENTS_DDL)
    if not _column_exists(conn, "schedules", "debt_id"):
        conn.execute("ALTER TABLE schedules ADD COLUMN debt_id INTEGER REFERENCES debts(id)")
    for statement in INDEXES:
        conn.execute(statement)

    if "DEBT_IN" not in _transactions_sql(conn):
        _rebuild_transactions(conn)
    if "DEBT_IN" not in _view_sql(conn):
        conn.execute("DROP VIEW IF EXISTS transaction_cash_flows")
        conn.execute(VIEW_DDL)
    conn.commit()


def verify(conn) -> bool:
    if not all(_table_exists(conn, name) for name in ("debts", "debt_rates", "debt_plan_entries", "debt_payments")):
        return False
    if not _column_exists(conn, "schedules", "debt_id"):
        return False
    sql = _transactions_sql(conn)
    return "DEBT_IN" in sql and "DEBT_OUT" in sql and "DEBT_IN" in _view_sql(conn)
