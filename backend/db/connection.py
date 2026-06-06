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
