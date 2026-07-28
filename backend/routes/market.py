from fastapi import APIRouter, HTTPException

from db import queries
from db.connection import get_db
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
async def sync_prices():
    """Fetch current prices for all active portfolio assets' market codes
    from the external Market API and store them in the prices table."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT pa.market_code
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE pa.is_active = 1
    """).fetchall()

    if not rows:
        return {"synced": 0, "results": []}

    client = get_market_client()
    results = []
    synced = 0
    from datetime import date as _date

    for row in rows:
        market_code = row["market_code"]
        try:
            data = client.get_all(market_code)
        except (MarketAPIUnavailable, MarketAPINotFound, MarketAPIError) as e:
            results.append({"market_code": market_code, "price": None, "error": str(e)})
            continue

        current_price = data.get("price")
        if current_price is not None:
            try:
                today = _date.today().isoformat()
                queries.create_price(
                    conn,
                    market_code=market_code,
                    timestamp=today,
                    price=float(current_price),
                    provider="market-api",
                )
                synced += 1
                results.append({"market_code": market_code, "price": current_price})
            except Exception:
                results.append({"market_code": market_code, "price": None, "error": "duplicate"})
                continue

        history = data.get("history", {})
        for date_str, ohlcv in sorted(history.items()):
            close = ohlcv.get("Close")
            if close is None:
                continue
            try:
                queries.create_price(
                    conn,
                    market_code=market_code,
                    timestamp=date_str,
                    price=float(close),
                    provider="market-api",
                )
                synced += 1
            except Exception:
                continue

    conn.commit()
    return {"synced": synced, "results": results}
