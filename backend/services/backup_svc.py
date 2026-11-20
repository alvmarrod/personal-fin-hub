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

import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from datetime import time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db.connection import DB_PATH
from services.activity_svc import tracked

logger = logging.getLogger(__name__)

BACKUP_FILE_RE = re.compile(r"^finhub\.db-\d{8}-\d{6}\.bak$")
MANIFEST_NAME = "manifest.json"


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
    """Resolve the backup timezone, never raising.

    Priority: ``BACKUP_TIMEZONE`` (if valid IANA), then the standard ``TZ``
    env var (if valid IANA), then the container's local timezone. An
    unresolvable name logs a warning and falls through instead of crashing
    startup.
    """
    for source, name in (
        ("BACKUP_TIMEZONE", os.environ.get("BACKUP_TIMEZONE")),
        ("TZ", os.environ.get("TZ")),
    ):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            logger.warning("Invalid %s=%r, falling back to container timezone", source, name)
    return datetime.now().astimezone().tzinfo


def backup_cron() -> str:
    return os.environ.get("BACKUP_CRON", "03:00")


def backup_cron_parts() -> tuple[int, int]:
    hour, minute = backup_cron().split(":")
    return int(hour), int(minute)


def _filename(now: datetime) -> str:
    return f"finhub.db-{now:%Y%m%d-%H%M%S}.bak"


# ---------------------------------------------------------------------------
# Metadata manifest
# ---------------------------------------------------------------------------


def _manifest_path() -> Path:
    return backup_dir() / MANIFEST_NAME


def _read_manifest() -> dict[str, dict[str, Any]]:
    """Manifest entries by filename. A missing or corrupt file is an empty
    manifest: listing still works from the directory itself."""
    path = _manifest_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("Backup manifest unreadable, ignoring: %s", path)
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def _write_manifest(entries: dict[str, dict[str, Any]]) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{MANIFEST_NAME}.tmp")
    tmp.write_text(json.dumps({"version": 1, "entries": entries}, indent=2, sort_keys=True))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _app_version() -> str:
    try:
        from services.update_svc import backend_version

        return backend_version()
    except Exception:
        return "unknown"


def _record(path: Path, tag: str) -> None:
    entries = _read_manifest()
    entries[path.name] = {
        "tag": tag,
        "app_version": _app_version(),
        "created_at": datetime.fromtimestamp(path.stat().st_mtime, backup_timezone()).isoformat(),
    }
    _write_manifest(entries)


def _forget(names: list[str]) -> None:
    entries = _read_manifest()
    removed = [name for name in names if entries.pop(name, None) is not None]
    if removed:
        _write_manifest(entries)


def backup_record(path: Path, latest: bool = False) -> dict[str, Any]:
    """Public description of one backup file. Never exposes the directory."""
    meta = _read_manifest().get(path.name, {})
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "created_at": meta.get("created_at") or datetime.fromtimestamp(stat.st_mtime, backup_timezone()).isoformat(),
        "tag": meta.get("tag"),
        "app_version": meta.get("app_version"),
        "latest": latest,
    }


def backup_records() -> list[dict[str, Any]]:
    """Every backup on disk, newest first."""
    return [backup_record(path, index == 0) for index, path in enumerate(list_backups())]


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

    _record(target, tag)
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


def prune_backups(retention: int | None = None, exclude: set[str] | None = None) -> list[Path]:
    """Delete backups beyond retention (default: ``BACKUP_RETENTION``).

    ``exclude`` names files that must survive this pass — a restore must not
    delete the backup it is about to read.
    """
    retention = retention if retention is not None else backup_retention()
    backups = [path for path in list_backups() if not (exclude and path.name in exclude)]
    removed = backups[retention:]
    for path in removed:
        path.unlink(missing_ok=True)
    _forget([path.name for path in removed])
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


@tracked("Daily backup")
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


def restore_plan(path: Path) -> dict[str, list[str]]:
    """Schema migrations needed to bring ``path`` up to this build.

    ``unknown`` lists versions recorded in the backup but absent from this
    build's migrations directory — restoring those is a downgrade and is
    refused by the caller.
    """
    from db.connection import migration_versions

    try:
        conn = sqlite3.connect(str(path))
        try:
            recorded = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        finally:
            conn.close()
    except sqlite3.Error:
        recorded = set()

    known = set(migration_versions())
    return {
        "missing": sorted(known - recorded),
        "unknown": sorted(recorded - known),
    }


def restore_from_backup(path: Path, dest: Path | None = None) -> Path:
    """Copy a verified backup over the live database and re-verify it.

    Uses the SQLite online-backup API instead of a file copy, so it is safe
    while the process holds the database open. The caller must still stop
    scheduled writers and verify the source first."""
    if not verify_backup(path):
        raise BackupError(f"Backup {path} failed verification; refusing to restore")
    dest = dest or DB_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(str(path))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    os.chmod(dest, 0o600)
    if not verify_backup(dest):
        raise BackupError(f"Restore produced an invalid database at {dest}")
    logger.info("Restored %s to %s", path.name, dest)
    return dest
