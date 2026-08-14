from fastapi import APIRouter, Query

from services.update_svc import get_update_status

router = APIRouter()


@router.get("/updates")
async def updates(frontend_version: str | None = Query(default=None)):
    """Report whether a newer backend/frontend release exists upstream.

    Public endpoint (no profile required). The frontend self-reports its own
    version via ``frontend_version`` since the static nginx container exposes
    no version to the backend otherwise.
    """
    return get_update_status(frontend_version=frontend_version)
