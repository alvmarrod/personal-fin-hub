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

    Migrations that are now baked into schema.sql have been removed.
    """

    # Drop deprecated purchase_date column from portfolio_assets
    cursor = conn.execute("PRAGMA table_info(portfolio_assets)")
    pa_cols = [row["name"] for row in cursor.fetchall()]
    if "purchase_date" in pa_cols:
        conn.execute("ALTER TABLE portfolio_assets DROP COLUMN purchase_date")
        conn.commit()
        logger.info("Migration: dropped purchase_date column from portfolio_assets")

    # Backfill auto-snapshots for existing INVESTMENT_BUY transactions
    _backfill_auto_snapshots(conn)

    # Create stock_splits table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_code TEXT NOT NULL,
            split_date TEXT NOT NULL,
            ratio INTEGER NOT NULL CHECK (ratio >= 2),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (market_code) REFERENCES market_assets(market_code)
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_split_year
        ON stock_splits(market_code, substr(split_date, 1, 4))
    """)
    conn.commit()

    # Add portfolio_asset_id column to schedules table
    cursor = conn.execute("PRAGMA table_info(schedules)")
    schedules_cols = [row["name"] for row in cursor.fetchall()]
    if "portfolio_asset_id" not in schedules_cols:
        conn.execute("ALTER TABLE schedules ADD COLUMN portfolio_asset_id INTEGER REFERENCES portfolio_assets(id)")
        conn.commit()
        logger.info("Migration: added portfolio_asset_id column to schedules")

    # Create manual_values table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS manual_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_asset_id INTEGER NOT NULL REFERENCES portfolio_assets(id),
            value REAL NOT NULL,
            effective_date DATE NOT NULL,
            recorded_at DATETIME NOT NULL DEFAULT (datetime('now')),
            notes TEXT,
            UNIQUE(portfolio_asset_id, effective_date)
        )
    """)
    conn.commit()


def _backfill_auto_snapshots(conn: sqlite3.Connection) -> None:
    """One-time migration: ensure every INVESTMENT_BUY has sufficient cash.

    Processes all INVESTMENT_BUY transactions in chronological order. If the
    cash balance at (timestamp - 1 day) is insufficient to cover a buy, creates
    a balance snapshot with the shortfall amount. Mirrors the runtime logic in
    transaction_svc._ensure_cash_for_buy but uses inline SQL for the migration
    context."""
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    buys = conn.execute("""
        SELECT id, entity_id, currency, total_value, timestamp
        FROM transactions
        WHERE type = 'INVESTMENT_BUY' AND total_value IS NOT NULL
        ORDER BY timestamp ASC
    """).fetchall()

    if not buys:
        return

    created = 0
    for buy in buys:
        eid = buy["entity_id"]
        currency = buy["currency"]
        total_value = buy["total_value"]
        ts_str = buy["timestamp"]
        ts = _dt.fromisoformat(ts_str) if "T" in ts_str else _dt.strptime(ts_str, "%Y-%m-%d")
        snapshot_ts = (ts - _td(days=1)).isoformat()

        # Compute cash balance at snapshot_ts (excluding this buy and future buys)
        balance = _compute_balance_at(conn, eid, currency, snapshot_ts)

        if balance >= total_value:
            continue

        needed = total_value - balance
        conn.execute(
            """INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp, notes)
               VALUES (?, ?, ?, ?, 'Auto-migrated: inferred cash for investment purchase')""",
            (eid, currency, needed, snapshot_ts),
        )
        created += 1
        logger.info(
            "Migration: backfilled auto-snapshot for entity %s / %s at %s (amount=%s of %s needed)",
            eid,
            currency,
            snapshot_ts,
            needed,
            total_value,
        )

    if created:
        conn.commit()


def _compute_balance_at(conn: sqlite3.Connection, entity_id: int, currency: str, timestamp: str) -> float:
    """Compute cash balance at a timestamp. Uses the same algorithm as
    queries.get_balance_at_date: starts from the most recent snapshot before
    the timestamp and adds transaction net flows, or sums all transactions
    if no previous snapshot exists."""
    prev = conn.execute(
        """SELECT amount, timestamp FROM balance_snapshots
           WHERE entity_id = ? AND currency = ? AND timestamp <= ?
           ORDER BY timestamp DESC LIMIT 1""",
        (entity_id, currency, timestamp),
    ).fetchone()

    if prev:
        balance = prev["amount"]
        txns = conn.execute(
            """SELECT type, total_value FROM transactions
               WHERE entity_id = ? AND currency = ?
                 AND timestamp > ? AND timestamp <= ?
               ORDER BY timestamp ASC""",
            (entity_id, currency, prev["timestamp"], timestamp),
        ).fetchall()
        for tx in txns:
            if tx["type"] in ("MONEY_IN", "INTEREST", "DIVIDEND", "INVESTMENT_SELL"):
                balance += tx["total_value"]
            elif tx["type"] in ("MONEY_OUT", "INVESTMENT_BUY"):
                balance -= tx["total_value"]
        return balance

    row = conn.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -total_value
                ELSE 0
            END
        ), 0) AS balance
        FROM transactions
        WHERE entity_id = ? AND currency = ? AND timestamp <= ?
    """,
        (entity_id, currency, timestamp),
    ).fetchone()
    return row["balance"] if row else 0.0


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
