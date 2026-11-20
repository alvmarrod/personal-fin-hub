"""Restore a verified backup into the live database.

Only called from the backups API. The flow is deliberately conservative:

1. refuse while any tracked background job is running,
2. open the maintenance window (other API requests get 503),
3. stop the scheduler and wait for running jobs,
4. snapshot the current database as ``pre-restore``,
5. copy the backup content into the live DB (SQLite online backup API),
6. apply pending migrations, restart the scheduler.

A failure before step 5 leaves the live database untouched; a failure after
it is recoverable from the ``pre-restore`` backup.
"""

import logging
import threading
from pathlib import Path

from services import activity_svc, backup_svc
from services.backup_svc import BackupError

logger = logging.getLogger(__name__)

_restore_lock = threading.Lock()


class RestoreBusy(RuntimeError):
    """Raised when background work is still writing to the database."""

    def __init__(self, running: list[dict[str, str]]):
        super().__init__("Background work in progress")
        self.running = running


def _pause_scheduler() -> None:
    try:
        from scheduler.scheduler import shutdown_scheduler

        shutdown_scheduler(wait=True)
    except Exception as e:
        raise BackupError("Could not stop background jobs; nothing was restored") from e


def _resume_scheduler() -> None:
    try:
        from scheduler.scheduler import init_scheduler

        init_scheduler()
    except Exception:
        logger.exception("Could not restart the scheduler after restore")


def _apply_migrations() -> list[str]:
    from db.connection import apply_migrations, get_db

    conn = get_db()
    try:
        return apply_migrations(conn)
    finally:
        conn.close()


def restore(path: Path) -> dict[str, object]:
    """Replace the live database with ``path``. Blocking and single-flight."""
    with _restore_lock:
        busy = activity_svc.running()
        if busy:
            raise RestoreBusy(busy)

        with activity_svc.maintenance():
            _pause_scheduler()
            try:
                pre = backup_svc.create_backup("pre-restore")
                pruned = backup_svc.prune_backups(exclude={path.name})
                backup_svc.restore_from_backup(path)
                applied = _apply_migrations()
            finally:
                _resume_scheduler()

            return {
                "restored": path.name,
                "pre_restore": pre.name,
                "pruned": [p.name for p in pruned],
                "migrations": applied,
            }
