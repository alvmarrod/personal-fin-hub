"""Backup listing, download, creation and restore.

System-level routes: backups span every profile, so these do not require the
``X-Profile-ID`` header.
"""

import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from services import activity_svc, backup_svc, restore_svc
from services.backup_svc import BackupError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backups", tags=["backups"])

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
_FILENAME_RE = re.compile(r"^finhub\.db-(\d{8})-(\d{6})\.bak$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve(name: str) -> Path:
    """A backup path inside the backup directory, or 404."""
    if not backup_svc.BACKUP_FILE_RE.match(name):
        raise HTTPException(status_code=404, detail="Backup not found")
    directory = backup_svc.backup_dir().resolve()
    path = (directory / name).resolve()
    if path.parent != directory or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    return path


def _policy() -> dict[str, object]:
    from scheduler.scheduler import current_scheduler

    next_run = None
    scheduler = current_scheduler()
    if scheduler is not None and scheduler.running:
        job = scheduler.get_job("backup_daily")
        if job is not None and job.next_run_time is not None:
            next_run = job.next_run_time.isoformat()

    tz = backup_svc.backup_timezone()
    return {
        "enabled": backup_svc.backup_enabled(),
        "cron": backup_svc.backup_cron(),
        "timezone": getattr(tz, "key", str(tz)),
        "retention": backup_svc.backup_retention(),
        "next_run_at": next_run,
    }


def _created_at_from_name(name: str) -> str | None:
    match = _FILENAME_RE.match(name)
    if not match:
        return None
    stamp = datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
    return stamp.replace(tzinfo=backup_svc.backup_timezone()).isoformat()


async def _save_upload(request: Request) -> tuple[Path, str]:
    """Stream the request body into a temp file inside the backup directory.

    Never trusts the declared length alone: the stream is capped as it is
    written. The temp name does not match the backup pattern, so it can never
    be listed, downloaded or restored by name.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None

    original = Path(request.headers.get("x-filename", "backup.bak")).name[:120] or "backup.bak"
    directory = backup_svc.backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f".upload-{uuid.uuid4().hex}.tmp"

    size = 0
    try:
        with path.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File is too large")
                handle.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise

    if size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty upload")

    os.chmod(path, 0o600)
    return path, original


def _plan(path: Path) -> list[str]:
    plan = backup_svc.restore_plan(path)
    if plan["unknown"]:
        raise HTTPException(
            status_code=400,
            detail="This backup was created by a newer version and cannot be restored here",
        )
    return plan["missing"]


def _inspect(path: Path, original: str) -> dict[str, object]:
    if not backup_svc.verify_backup(path):
        raise HTTPException(status_code=400, detail="This file is not a valid finhub database")

    migrations = _plan(path)
    return {
        "name": original,
        "size": path.stat().st_size,
        "created_at": _created_at_from_name(original),
        "migrations": migrations,
    }


def _restore(path: Path) -> dict[str, object]:
    try:
        return restore_svc.restore(path)
    except restore_svc.RestoreBusy as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "Background work is still running", "activity": e.running},
        ) from e
    except BackupError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Routes — fixed paths first, then the ``{name}`` routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_backups() -> dict[str, object]:
    return {"policy": _policy(), "items": backup_svc.backup_records()}


@router.get("/activity")
async def backup_activity() -> dict[str, object]:
    return {"busy": activity_svc.running()}


@router.post("", status_code=201)
async def create_backup() -> dict[str, object]:
    try:
        path = backup_svc.create_backup("manual")
    except BackupError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    pruned = backup_svc.prune_backups()
    return {
        "created": backup_svc.backup_record(path),
        "pruned": [item.name for item in pruned],
    }


@router.post("/inspect")
async def inspect_backup(request: Request) -> dict[str, object]:
    path, original = await _save_upload(request)
    try:
        return _inspect(path, original)
    finally:
        path.unlink(missing_ok=True)


@router.post("/restore")
async def restore_uploaded(request: Request) -> dict[str, object]:
    path, _ = await _save_upload(request)
    try:
        return _restore(path)
    finally:
        path.unlink(missing_ok=True)


@router.post("/{name}/inspect")
async def inspect_existing(name: str) -> dict[str, object]:
    path = _resolve(name)
    record = backup_svc.backup_record(path)
    return {
        "name": path.name,
        "size": record["size"],
        "created_at": record["created_at"],
        "migrations": _plan(path),
        "tag": record["tag"],
    }


@router.post("/{name}/restore")
async def restore_existing(name: str) -> dict[str, object]:
    return _restore(_resolve(name))


@router.get("/{name}")
async def download_backup(name: str) -> FileResponse:
    path = _resolve(name)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
