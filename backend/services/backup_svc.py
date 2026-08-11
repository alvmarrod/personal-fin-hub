"""Online-safe SQLite backups.

The database is a single SQLite file in rollback-journal mode; a plain file
copy while the app is writing can capture a torn, unusable copy. Backups are
produced with the stdlib ``sqlite3.Connection.backup()`` API, which is
consistent under concurrent writes, then verified with ``PRAGMA
integrity_check`` and pruned to the newest N files.

Config (env vars):

- ``BACKUP_ENABLED`` — set to ``0`` to disable (default ``1``)
- ``BACKUP_DIR`` — destination directory (default ``<db dir>/backups``)
- ``BACKUP_TIMEZONE`` — IANA name, e.g. ``Asia/Tokyo`` (default: system local)
- ``BACKUP_CRON`` — ``HH:MM`` local to ``BACKUP_TIMEZONE`` (default ``03:00``)
- ``BACKUP_RETENTION`` — number of backups to keep (default 7)
"""

import logging
import os
import re
import shutil
import sqlite3
import time
from datetime import datetime
from datetime import time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from db.connection import DB_PATH

logger = logging.getLogger(__name__)

BACKUP_FILE_RE = re.compile(r"^finhub\.db-\d{8}-\d{6}\.bak$")


class BackupError(RuntimeError):
    """Raised when a backup or restore cannot be completed safely."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def backup_enabled() -> bool:
    return _env_bool("BACKUP_ENABLED", True)


def backup_retention() -> int:
    return max(1, _env_int("BACKUP_RETENTION", 7))


def backup_dir() -> Path:
    raw = os.environ.get("BACKUP_DIR")
    if raw:
        return Path(raw)
    return DB_PATH.parent / "backups"


def backup_timezone() -> Any:
    name = os.environ.get("BACKUP_TIMEZONE")
    if name:
        return ZoneInfo(name)
    return datetime.now().astimezone().tzinfo


def backup_cron() -> str:
    return os.environ.get("BACKUP_CRON", "03:00")


def backup_cron_parts() -> tuple[int, int]:
    hour, minute = backup_cron().split(":")
    return int(hour), int(minute)


def _filename(now: datetime) -> str:
    return f"finhub.db-{now:%Y%m%d-%H%M%S}.bak"


# ---------------------------------------------------------------------------
# Backup lifecycle
# ---------------------------------------------------------------------------


def create_backup(tag: str = "manual") -> Path:
    """Create a verified backup of the live database. Returns the backup path."""
    if not DB_PATH.exists():
        raise BackupError(f"Database not found at {DB_PATH}")
    if DB_PATH.stat().st_size == 0:
        raise BackupError(f"Database at {DB_PATH} is empty; refusing to back up")

    target = backup_dir() / _filename(datetime.now(backup_timezone()))
    target.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    os.chmod(target, 0o600)

    if not verify_backup(target):
        target.unlink(missing_ok=True)
        raise BackupError(f"Backup {target.name} failed integrity verification")

    logger.info(
        "Backup created: %s (%d bytes, %.1fs) [%s]",
        target.name,
        target.stat().st_size,
        time.monotonic() - started,
        tag,
    )
    return target


def verify_backup(path: Path) -> bool:
    """Return True if the file is a valid, consistent SQLite database."""
    try:
        conn = sqlite3.connect(str(path))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                logger.error("Backup %s integrity check failed: %s", path.name, row)
                return False
            for table in ("profiles", "entities", "transactions"):
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return True
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Backup %s could not be verified: %s", path.name, e)
        return False


def list_backups() -> list[Path]:
    """Backup files, newest first."""
    directory = backup_dir()
    if not directory.exists():
        return []
    return sorted((p for p in directory.glob("finhub.db-*.bak") if BACKUP_FILE_RE.match(p.name)), reverse=True)


def latest_backup() -> Path | None:
    backups = list_backups()
    return backups[0] if backups else None


def prune_backups(retention: int | None = None) -> list[Path]:
    """Delete backups beyond retention (default: ``BACKUP_RETENTION``)."""
    retention = retention if retention is not None else backup_retention()
    backups = list_backups()
    removed = backups[retention:]
    for path in removed:
        path.unlink(missing_ok=True)
    if removed:
        logger.info("Pruned %d backup(s) (retention=%d)", len(removed), retention)
    return removed


def is_daily_due(now: datetime | None = None) -> bool:
    """True when past the daily cron time (in ``BACKUP_TIMEZONE``) and no
    backup exists for the current day."""
    tz = backup_timezone()
    now = now.astimezone(tz) if now is not None else datetime.now(tz)
    hour, minute = backup_cron_parts()
    cutoff = datetime.combine(now.date(), dt_time(hour, minute), tzinfo=tz)
    if now < cutoff:
        return False
    prefix = f"finhub.db-{now:%Y%m%d}"
    return not any(p.name.startswith(prefix) for p in list_backups())


def run_daily_backup() -> None:
    """Scheduler entry point: create today's backup and prune."""
    if not backup_enabled():
        return
    create_backup("daily")
    prune_backups()


def startup_daily_backup() -> bool:
    """Daily catch-up on startup, BEFORE anything else touches the DB.

    Creates a backup when past the daily cron time and none exists for today.
    Returns True if a backup was created (its file then doubles as the
    pre-migration state when migrations run later this boot)."""
    if not backup_enabled():
        return False
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return False
    if not is_daily_due():
        return False
    create_backup("daily-catchup")
    return True


def migration_backups(fresh: bool, applied: list[str], daily_ran: bool) -> list[Path]:
    """Create pre/post migration backups when migrations were applied.

    ``fresh`` True means the schema was created from scratch this boot (no
    data to protect) and ``applied`` the migration versions whose ``up()``
    ran. When the daily catch-up already produced a backup this boot, it IS
    the pre-migration state and is not duplicated."""
    if not backup_enabled() or fresh or not applied:
        return []
    created = []
    if not daily_ran:
        created.append(create_backup("pre-migration"))
    created.append(create_backup("post-migration"))
    prune_backups()
    return created


def backup_info() -> dict:
    """Public-safe summary for /health (no paths)."""
    if not backup_enabled():
        return {"enabled": False, "status": "disabled", "latest": None}
    latest = latest_backup()
    if latest is None:
        return {"enabled": True, "status": "never", "latest": None}
    status = "stale" if is_daily_due() else "ok"
    return {
        "enabled": True,
        "status": status,
        "latest": latest.name,
        "latest_at": datetime.fromtimestamp(latest.stat().st_mtime, backup_timezone()).isoformat(),
    }


def restore_from_backup(path: Path, dest: Path | None = None) -> Path:
    """Copy a verified backup over the live database and re-verify it.

    ``dest`` defaults to ``DB_PATH``. The caller (CLI) is responsible for
    ensuring the backend is stopped first."""
    if not verify_backup(path):
        raise BackupError(f"Backup {path} failed verification; refusing to restore")
    dest = dest or DB_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    os.chmod(dest, 0o600)
    if not verify_backup(dest):
        raise BackupError(f"Restore produced an invalid database at {dest}")
    logger.info("Restored %s to %s", path.name, dest)
    return dest
