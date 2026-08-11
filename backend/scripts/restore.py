"""Restore the database from a backup. Run from the backend dir:

    uv run python -m scripts.restore [BACKUP_PATH]

The backend must be stopped first: the script refuses to run while
/api/v1/health is reachable (pass --force to override at your own risk).
Backs up the current (broken) database before overwriting it.
"""

import argparse
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from db.connection import DB_PATH
from services.backup_svc import BackupError, latest_backup, restore_from_backup, verify_backup

HEALTH_URL = "http://localhost:8000/api/v1/health"


def backend_running() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
            return resp.status < 500
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore the database from a verified backup")
    parser.add_argument("backup", nargs="?", help="backup file to restore (default: newest)")
    parser.add_argument("--force", action="store_true", help="restore even if the backend is reachable")
    args = parser.parse_args()

    if backend_running() and not args.force:
        print(
            f"error: backend appears to be running ({HEALTH_URL} reachable). Stop it first or pass --force.",
            file=sys.stderr,
        )
        return 1

    path: Path | None = Path(args.backup) if args.backup else latest_backup()
    if path is None:
        print("error: no backups found", file=sys.stderr)
        return 1

    if not path.exists():
        print(f"error: backup not found: {path}", file=sys.stderr)
        return 1

    if not verify_backup(path):
        print(f"error: backup failed verification, refusing to restore: {path}", file=sys.stderr)
        return 1

    if DB_PATH.exists():
        rescue = DB_PATH.parent / f"finhub.db.pre-restore-{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(DB_PATH, rescue)
        print(f"current database preserved at: {rescue}")

    try:
        restore_from_backup(path)
    except BackupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"restored: {path}")
    print("start the backend to verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
