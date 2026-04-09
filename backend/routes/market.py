from fastapi import APIRouter, HTTPException

from services.api_client import (
    MarketAPIClient,
    MarketAPIError,
    MarketAPIUnavailable,
    MarketAPINotFound,
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
        raise HTTPException(status_code=503, detail=str(e))
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/price")
async def get_price(symbol: str):
    """Fetch current price for a symbol."""
    client = get_market_client()
    try:
        return client.get_price(symbol)
    except MarketAPIUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/{field}")
async def get_field(symbol: str, field: str):
    """Fetch a specific field's value for a symbol."""
    client = get_market_client()
    try:
        return client.get_field(symbol, field)
    except MarketAPIUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MarketAPINotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MarketAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
