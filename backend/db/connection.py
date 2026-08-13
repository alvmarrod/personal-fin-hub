import datetime
import logging
import sqlite3
from contextvars import ContextVar, Token
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "finhub.db"

logger = logging.getLogger(__name__)

# Tables whose data belongs to a single profile (user-created data).
# Market reference data (currencies, market_assets, prices, stock_splits)
# and scheduler_state are shared and intentionally NOT listed here.
PROFILE_TABLES = [
    "entities",
    "transactions",
    "transaction_fees",
    "transaction_taxes",
    "portfolio_assets",
    "balance_snapshots",
    "schedules",
    "schedule_occurrences",
    "manual_values",
    "fiscal_exemptions",
]

PROFILES_DDL = """
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        password_hash TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""


class ProfileScopedConnection(sqlite3.Connection):
    """Connection that carries the active profile_id for row-scoped queries."""

    def __init__(self, *args, **kwargs):
        self.profile_id: int | None = None
        super().__init__(*args, **kwargs)


# Active profile for the current request context. Set by the X-Profile-ID
# dependency; read by get_db() when no explicit profile_id is passed.
_active_profile_id: ContextVar[int | None] = ContextVar("active_profile_id", default=None)


def set_active_profile(profile_id: int | None) -> Token:
    return _active_profile_id.set(profile_id)


def reset_active_profile(token: Token) -> None:
    _active_profile_id.reset(token)


def get_db(profile_id: int | None = None) -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    sqlite3.register_adapter(datetime.datetime, lambda v: v.isoformat())
    conn = sqlite3.connect(DB_PATH, factory=ProfileScopedConnection)
    conn.row_factory = sqlite3.Row
    conn.profile_id = profile_id if profile_id is not None else _active_profile_id.get()
    return conn


def _run_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply pending schema migrations in version order.

    Reads migration modules from db/migrations/ and applies any that have not
    reached their verified end-state. Each migration module must export:
    ``up(conn)`` (an idempotent apply) and ``verify(conn)`` (True iff the
    migration's end-state is present).

    ``verify`` is the source of truth; the schema_migrations tracking table is
    only a cache. A migration recorded as applied but whose end-state is
    missing (e.g. a bad bootstrap) is re-applied automatically on next boot.

    Returns the list of versions whose ``up()`` ran this call (empty when the
    database was already fully migrated).
    """
    from importlib import import_module

    # Ensure tracking table exists (bootstrap for very old DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(f for f in migrations_dir.iterdir() if f.suffix == ".py" and f.stem[0].isdigit())

    applied_versions: list[str] = []

    for f in files:
        version = f.stem
        mod = import_module(f"db.migrations.{version}")
        if not hasattr(mod, "verify"):
            raise RuntimeError(f"Migration {version} must define verify(conn)")

        applied = conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone()
        if applied and mod.verify(conn):
            continue

        mod.up(conn)
        if not mod.verify(conn):
            raise RuntimeError(f"Migration {version} did not reach its verified end-state")
        conn.execute("INSERT OR REPLACE INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
        applied_versions.append(version)
        logger.info("Migration %s: applied", version)

    return applied_versions


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _migrate_profiles(conn: sqlite3.Connection) -> None:
    """Add multi-profile support.

    Creates the ``profiles`` table, seeds a passwordless default profile, and
    scopes user-created data by adding + backfilling a ``profile_id`` column on
    every ownership table. Market reference data (currencies, market_assets,
    prices, stock_splits) and scheduler_state are left untouched. Idempotent.
    """
    conn.execute(PROFILES_DDL)
    conn.execute(
        "INSERT INTO profiles (name, password_hash) SELECT 'Default', NULL WHERE NOT EXISTS (SELECT 1 FROM profiles)"
    )
    default_id = conn.execute("SELECT id FROM profiles ORDER BY id ASC LIMIT 1").fetchone()["id"]

    for table in PROFILE_TABLES:
        if not _table_exists(conn, table):
            continue
        if not _column_exists(conn, table, "profile_id"):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN profile_id INTEGER REFERENCES profiles(id)")
        conn.execute(f"UPDATE {table} SET profile_id = ? WHERE profile_id IS NULL", (default_id,))
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_profile ON {table}(profile_id)")
        conn.commit()

    logger.info(
        "Migration: added profile_id to %d ownership tables, default profile id=%s", len(PROFILE_TABLES), default_id
    )


def _migrate_transactions_check(conn: sqlite3.Connection) -> None:
    """Widen the transactions.type CHECK constraint.

    SQLite cannot alter a CHECK constraint in place, so the transactions table
    is rebuilt with the new constraint when the old one is detected. Data and
    foreign keys are preserved (child tables reference transactions by name,
    which is restored by the RENAME).
    """
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'").fetchone()
    if row is None or "TRANSFER_IN" in row["sql"]:
        return

    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("""
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT')),
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
                notes TEXT,
                profile_id INTEGER REFERENCES profiles(id)
            )
        """)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall())
        conn.execute(f"INSERT INTO transactions_new ({cols}) SELECT {cols} FROM transactions")
        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id)")
        conn.commit()
        logger.info("Migration: rebuilt transactions table with TRANSFER_IN/TRANSFER_OUT CHECK")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={foreign_keys}")


def _migrate_schedule_occurrences(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_occurrences'").fetchone()
    if row is None:
        conn.execute("""
            CREATE TABLE schedule_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                occurrence_date TEXT NOT NULL,
                transaction_id INTEGER NOT NULL,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            )
        """)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_occurrence ON schedule_occurrences(schedule_id, occurrence_date)"
        )
        conn.commit()
        logger.info("Migration: created schedule_occurrences table")

        _backfill_schedule_occurrences(conn)


def _backfill_schedule_occurrences(conn: sqlite3.Connection) -> None:
    import re

    rows = conn.execute("SELECT id, timestamp, notes FROM transactions WHERE notes LIKE '%[schedule:%]'").fetchall()
    if not rows:
        return
    inserted = 0
    for r in rows:
        m = re.search(r"\[schedule:(\d+)\]", r["notes"] or "")
        if not m:
            continue
        schedule_id = int(m.group(1))
        occ_date = r["timestamp"].split("T")[0] if "T" in r["timestamp"] else r["timestamp"].split(" ")[0]
        try:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO schedule_occurrences (schedule_id, occurrence_date, transaction_id) VALUES (?, ?, ?)",
                (schedule_id, occ_date, r["id"]),
            )
            if cursor.rowcount and cursor.rowcount > 0:
                inserted += 1
        except Exception:
            pass
    if inserted:
        conn.commit()
        logger.info("Migration: backfilled %d existing schedule occurrences", inserted)


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
            if tx["type"] in ("INCOME", "INVESTMENT_SELL", "TRANSFER_IN"):
                balance += tx["total_value"]
            elif tx["type"] in ("MONEY_OUT", "INVESTMENT_BUY", "TRANSFER_OUT"):
                balance -= tx["total_value"]
        return balance

    row = conn.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                ELSE 0
            END
        ), 0) AS balance
        FROM transactions
        WHERE entity_id = ? AND currency = ? AND timestamp <= ?
    """,
        (entity_id, currency, timestamp),
    ).fetchone()
    return row["balance"] if row else 0.0


def init_db() -> tuple[bool, list[str]]:
    """Initialize the schema and apply pending migrations.

    Returns ``(fresh, applied)``: ``fresh`` is True when the schema was
    created from scratch this boot, and ``applied`` lists the migration
    versions whose ``up()`` ran (empty when already up to date). Callers use
    this to decide whether pre/post migration backups are needed.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_db()
    cursor = conn.cursor()

    # Check if tables already exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    fresh = not existing_tables

    # Only run schema if no tables exist
    if fresh:
        conn.executescript(schema_path.read_text())

    # Apply incremental migrations regardless of DB age
    applied = _run_migrations(conn)

    conn.close()
    return fresh, applied
