from fastapi import APIRouter, HTTPException, Query

from db import queries
from db.analytics_queries import get_net_positions_as_of, get_all_prices, get_latest_transaction_prices
from db.connection import get_db
from models import PriceCreate, PriceResponse
from services.price_svc import (
    MarketAssetNotFound,
    PriceAlreadyExists,
    PriceError,
    PriceNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/value-chart")
async def portfolio_value_chart(
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Return holding value per market_code over time (net_quantity × price at each date)."""
    from bisect import bisect_right
    from collections import defaultdict
    from datetime import datetime as _dt, timedelta as _td

    conn = get_db()

    if not start_date:
        start_date = (_dt.now() - _td(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = _dt.now().strftime("%Y-%m-%d")

    start = _dt.strptime(start_date, "%Y-%m-%d")
    end = _dt.strptime(end_date, "%Y-%m-%d")

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in all_prices:
        price_index[p["market_code"]].append((p["timestamp"][:10], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])

    tx_fallback = {r["market_code"]: r["unit_price"] for r in get_latest_transaction_prices(conn)}

    def price_as_of(market_code: str, date_str: str) -> float | None:
        entries = price_index.get(market_code, [])
        if entries:
            dates = [e[0] for e in entries]
            idx = bisect_right(dates, date_str) - 1
            if idx >= 0:
                return entries[idx][1]
        return tx_fallback.get(market_code)

    # Get active portfolio assets
    assets = conn.execute("""
        SELECT pa.id, pa.market_code FROM portfolio_assets pa
        WHERE pa.is_active = 1 ORDER BY pa.market_code
    """).fetchall()

    by_asset: dict[str, list[dict]] = {a["market_code"]: [] for a in assets}
    # Also build a list of all dates (weekly)
    dates: list[str] = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += _td(days=7)

    for date_str in dates:
        positions = get_net_positions_as_of(conn, date_str + "T23:59:59")
        pos_map = {p["market_code"]: p["net_quantity"] for p in positions if p["net_quantity"] > 0}
        for a in assets:
            code = a["market_code"]
            qty = pos_map.get(code, 0)
            if qty <= 0:
                continue
            price = price_as_of(code, date_str)
            if price is None:
                continue
            by_asset[code].append({"date": date_str, "value": round(qty * price, 2)})

    return {k: v for k, v in by_asset.items() if v}


@router.get("/chart")
async def all_prices_chart(
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.market_code, p.timestamp, p.price
        FROM prices p
        JOIN portfolio_assets pa ON pa.market_code = p.market_code
        WHERE pa.is_active = 1
        ORDER BY p.market_code, p.timestamp ASC
    """).fetchall()

    by_asset: dict[str, list[dict]] = {}
    for r in rows:
        ts = r["timestamp"]
        if start_date and ts < start_date:
            continue
        if end_date and ts > end_date:
            continue
        code = r["market_code"]
        if code not in by_asset:
            by_asset[code] = []
        by_asset[code].append({"date": ts[:10], "price": r["price"]})

    return by_asset


@router.get("/chart/{market_code}")
async def price_chart(
    market_code: str,
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
):
    conn = get_db()
    rows = queries.get_prices_by_market(conn, market_code)
    points = []
    for r in rows:
        ts = r["timestamp"]
        if start_date and ts < start_date:
            continue
        if end_date and ts > end_date:
            continue
        points.append({"date": ts[:10], "price": r["price"]})
    points.sort(key=lambda p: p["date"])
    return points


@router.get("", response_model=list[PriceResponse])
async def list_prices(market_code: str | None = Query(None, description="Filter by market code")):
    return list_all(market_code)


@router.post("", response_model=PriceResponse, status_code=201)
async def create_price(body: PriceCreate):
    try:
        return create(body)
    except PriceAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (MarketAssetNotFound, PriceError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{price_id}", response_model=PriceResponse)
async def get_price(price_id: int):
    try:
        return get(price_id)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{price_id}", response_model=PriceResponse)
async def update_price(price_id: int, body: PriceCreate):
    try:
        return update(price_id, body)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (PriceAlreadyExists, MarketAssetNotFound, PriceError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{price_id}", status_code=204)
async def delete_price(price_id: int):
    try:
        delete(price_id)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
