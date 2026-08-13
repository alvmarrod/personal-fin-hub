from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from services.api_client import (
    MarketAPIError,
    MarketAPINotFound,
    MarketAPIUnavailable,
    get_market_client,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/health")
async def market_health():
    """Check if external Market API is available."""
    client = get_market_client()
    is_healthy = client.health_check()
    if is_healthy:
        return {"status": "healthy", "market_api": "available"}
    raise HTTPException(status_code=503, detail="Market API unavailable")


@router.get("/{symbol}")
async def get_symbol_data(symbol: str):
    """Fetch all available data for a symbol."""
    client = get_market_client()
    try:
        return client.get_all(symbol)
    except MarketAPIUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{symbol}/price")
async def get_price(symbol: str):
    """Fetch current price for a symbol."""
    client = get_market_client()
    try:
        return client.get_price(symbol)
    except MarketAPIUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{symbol}/{field}")
async def get_field(symbol: str, field: str):
    """Fetch a specific field's value for a symbol."""
    client = get_market_client()
    try:
        return client.get_field(symbol, field)
    except MarketAPIUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sync-prices")
async def sync_prices(
    full: bool = Query(False, description="Full refresh — ignore freshness skip"),
    pace: float = Query(2.0, description="Seconds to sleep between symbol requests"),
    max_age_hours: float = Query(1.0, description="Skip symbols fetched more recently than this (incremental only)"),
):
    """Fetch current prices for all active portfolio assets' market codes
    from the external Market API and store them in the prices table."""
    from services.market_sync_svc import sync_prices as _sync

    return await run_in_threadpool(_sync, full=full, pace=pace, max_age_hours=max_age_hours)
