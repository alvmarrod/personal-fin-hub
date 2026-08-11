from fastapi import APIRouter

from db.connection import get_db
from services.api_client import MarketAPIClient
from services.api_resilience import get_breaker
from services.backup_svc import backup_info
from services.config import config

router = APIRouter()


@router.get("/health")
async def health_check():
    checks: dict[str, str | None] = {}

    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        client = MarketAPIClient(timeout=2)
        ok = client.health_check()
        checks["market_api"] = "ok" if ok else "unreachable"
    except Exception as e:
        checks["market_api"] = f"error: {e}"

    # Circuit state is shared with the request path (per base_url) — read-only
    # here; the health probe above already fails fast when the circuit is open.
    breaker = get_breaker(config.market_api_base_url)
    checks["market_api_circuit"] = breaker.state.value
    checks["market_api_last_success_at"] = breaker.last_success_at

    # Newest stored market price — data freshness (distinct from API
    # availability): null until the first successful sync stores a price row.
    try:
        conn = get_db()
        row = conn.execute("SELECT MAX(timestamp) FROM prices").fetchone()
        conn.close()
        checks["market_data_last_updated"] = row[0]
    except Exception as e:
        checks["market_data_last_updated"] = f"error: {e}"

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
