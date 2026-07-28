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

    # Backfill auto-snapshots for existing INVESTMENT_BUY transactions
    _backfill_auto_snapshots(conn)


def _backfill_auto_snapshots(conn: sqlite3.Connection) -> None:
    """One-time migration: create anchor snapshots for entity+currency pairs that
    have INVESTMENT_BUY transactions but no balance snapshots and no MONEY_IN or
    BALANCE_ADJUSTMENT transactions. Mirrors the runtime auto-snapshot logic in
    transaction_svc._auto_snapshot_if_first_buy."""
    rows = conn.execute("""
        SELECT t.entity_id, t.currency,
               MIN(t.timestamp) AS earliest_ts,
               MIN(t.id) AS earliest_id
        FROM transactions t
        WHERE t.type = 'INVESTMENT_BUY'
          AND (t.entity_id, t.currency) NOT IN (
              SELECT DISTINCT entity_id, currency FROM balance_snapshots
          )
          AND (t.entity_id, t.currency) NOT IN (
              SELECT DISTINCT entity_id, currency FROM transactions
              WHERE type IN ('MONEY_IN', 'BALANCE_ADJUSTMENT')
          )
        GROUP BY t.entity_id, t.currency
    """).fetchall()

    if not rows:
        return

    for row in rows:
        eid = row["entity_id"]
        currency = row["currency"]
        earliest_ts = row["earliest_ts"]
        # Find the total_value of the earliest INVESTMENT_BUY for this pair
        buy = conn.execute("""
            SELECT total_value FROM transactions
            WHERE entity_id = ? AND currency = ? AND type = 'INVESTMENT_BUY'
            ORDER BY timestamp ASC LIMIT 1
        """, (eid, currency)).fetchone()
        if buy is None or buy["total_value"] is None:
            continue

        from datetime import datetime as _dt, timedelta as _td
        ts = _dt.fromisoformat(earliest_ts) if "T" in earliest_ts else _dt.strptime(earliest_ts, "%Y-%m-%d")
        snapshot_ts = (ts - _td(days=1)).isoformat()

        conn.execute(
            """INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp, notes)
               VALUES (?, ?, ?, ?, 'Auto-migrated: initial cash inferred from first investment purchase')""",
            (eid, currency, buy["total_value"], snapshot_ts),
        )
        logger.info(
            "Migration: backfilled auto-snapshot for entity %s / %s at %s (amount=%s)",
            eid, currency, snapshot_ts, buy["total_value"],
        )

    conn.commit()


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
