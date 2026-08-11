from fastapi import APIRouter

from db.connection import get_db
from services.api_client import MarketAPIClient
from services.backup_svc import backup_info

router = APIRouter()


@router.get("/health")
async def health_check():
    checks: dict[str, str] = {}

    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        client = MarketAPIClient(timeout=3)
        ok = client.health_check()
        checks["market_api"] = "ok" if ok else "unreachable"
    except Exception as e:
        checks["market_api"] = f"error: {e}"

    # Informational only — a stale backup degrades resilience but does not
    # make the service unhealthy. Never exposes backup paths.
    try:
        checks["backup"] = backup_info()["status"]
    except Exception as e:
        checks["backup"] = f"error: {e}"

    db_ok = checks.get("database") == "ok"
    api_ok = checks.get("market_api") == "ok"

    if not db_ok:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "checks": checks},
        )

    if not api_ok:
        return {
            "status": "degraded",
            "checks": checks,
        }

    return {"status": "healthy", "checks": checks}
