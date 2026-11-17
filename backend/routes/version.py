from fastapi import APIRouter

from services.update_svc import backend_version

router = APIRouter()


@router.get("/version")
async def version():
    """Public: the backend version this process was built from.

    Read from ``pyproject.toml`` at import time (``update_svc``), so it cannot
    drift from the shipped release. The UI shows it in the sidebar.
    """
    return {"version": backend_version()}
