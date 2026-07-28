import datetime
import logging
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "finhub.db"

logger = logging.getLogger(__name__)


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    sqlite3.register_adapter(datetime.datetime, lambda v: v.isoformat())
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    """
    Apply non-destructive schema migrations for existing databases.
    Uses PRAGMA table_info to check column existence before ALTER TABLE.

    Future: replace with a versioned migration system using a _schema_version table
    for ordered, reproducible migrations across environments.
    """
    cursor = conn.execute("PRAGMA table_info(entities)")
    columns = [row["name"] for row in cursor.fetchall()]

    if "deleted_at" not in columns:
        conn.execute("ALTER TABLE entities ADD COLUMN deleted_at DATETIME DEFAULT NULL")
        conn.commit()
        logger.info("Migration: added deleted_at column to entities")

    cursor = conn.execute("PRAGMA table_info(schedules)")
    sched_cols = [row["name"] for row in cursor.fetchall()]

    for col in ("entity_id", "currency", "type", "total_value", "notes"):
        if col not in sched_cols:
            conn.execute(f"ALTER TABLE schedules ADD COLUMN {col}")
            conn.commit()
            logger.info("Migration: added %s column to schedules", col)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduler_state'")
    if cursor.fetchone() is None:
        conn.execute(
            "CREATE TABLE scheduler_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.commit()
        logger.info("Migration: created scheduler_state table")

    # Recreate transactions table if CHECK constraint is missing BALANCE_ADJUSTMENT
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    )
    row = cursor.fetchone()
    if row and "BALANCE_ADJUSTMENT" not in row["sql"]:
        logger.info("Migration: recreating transactions table with BALANCE_ADJUSTMENT in CHECK constraint")
        conn.execute("BEGIN TRANSACTION")
        conn.execute("ALTER TABLE transactions RENAME TO transactions_old")
        conn.executescript("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('MONEY_IN', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'DIVIDEND', 'INTEREST', 'TRANSFER', 'BALANCE_ADJUSTMENT')),
                transaction_category TEXT CHECK (transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
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
                dividend_type TEXT CHECK (dividend_type IN ('regular', 'special', 'qualified')),
                record_date DATE,
                payment_date DATE,
                dividend_currency TEXT REFERENCES currencies(code),
                dividend_payment_currency TEXT REFERENCES currencies(code),
                dividend_fx_rate REAL,
                notes TEXT
            );
        """)
        conn.execute("""
            INSERT INTO transactions
                (id, timestamp, type, transaction_category, entity_id, portfolio_asset_id,
                 quantity, unit_price, currency, total_value, gross_amount, net_amount,
                 payment_currency, fx_rate, settlement_date, fiscal_exemption_id,
                 dividend_type, record_date, payment_date, dividend_currency,
                 dividend_payment_currency, dividend_fx_rate, notes)
            SELECT
                id, timestamp, type, transaction_category, entity_id, portfolio_asset_id,
                quantity, unit_price, currency, total_value, gross_amount, net_amount,
                payment_currency, fx_rate, settlement_date, fiscal_exemption_id,
                dividend_type, record_date, payment_date, dividend_currency,
                dividend_payment_currency, dividend_fx_rate, notes
            FROM transactions_old
        """)
        conn.execute("DROP TABLE transactions_old")
        conn.execute("COMMIT")
        logger.info("Migration: transactions table recreated with BALANCE_ADJUSTMENT support")


def init_db():
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_db()
    cursor = conn.cursor()

    # Check if tables already exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    # Only run schema if no tables exist
    if not existing_tables:
        conn.executescript(schema_path.read_text())

    # Apply incremental migrations regardless of DB age
    _run_migrations(conn)

    conn.close()
