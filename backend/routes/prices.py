from fastapi import APIRouter, HTTPException, Query

from db import queries
from db.analytics_queries import detect_stock_splits, get_all_prices, get_net_positions_as_of
from db.connection import get_db
from models import PriceCreate, PriceResponse
from services.price_svc import (
    MarketAssetNotFound,
    PriceAlreadyExists,
    PriceError,
    PriceNotFound,
    create,
    delete,
    get,
    list_all,
    update,
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
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    conn = get_db()

    if not start_date:
        earliest = conn.execute("""
            SELECT MIN(t) AS d FROM (
                SELECT MIN(timestamp) AS t FROM transactions
                UNION ALL
                SELECT MIN(timestamp) AS t FROM prices
            ) WHERE t IS NOT NULL
        """).fetchone()["d"]
        start_date = earliest[:10] if earliest else "2020-01-01"
    if not end_date:
        end_date = _dt.now().strftime("%Y-%m-%d")

    start = _dt.strptime(start_date, "%Y-%m-%d")
    end = _dt.strptime(end_date, "%Y-%m-%d")

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
    first_price: dict[str, float] = {}
    for p in all_prices:
        price_index[p["market_code"]].append((p["timestamp"][:10], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])
        first_price[mc] = price_index[mc][0][1]

    def price_as_of(market_code: str, date_str: str) -> float | None:
        entries = price_index.get(market_code, [])
        if entries:
            dates = [e[0] for e in entries]
            idx = bisect_right(dates, date_str) - 1
            if idx >= 0:
                return entries[idx][1]
        return None

    # Get ALL portfolio assets (including inactive, so historical holdings appear)
    assets = conn.execute("""
        SELECT pa.id, pa.market_code FROM portfolio_assets pa
        ORDER BY pa.market_code
    """).fetchall()

    by_asset: dict[str, list[dict]] = {a["market_code"]: [] for a in assets}

    # Detect stock splits and build per-market_code adjustment periods
    splits = detect_stock_splits(conn)
    split_periods: dict[str, list[tuple[str, str, float]]] = {}
    if splits:
        from collections import defaultdict as _dd

        # Group split ratios by (market_code, buy_date)
        buy_ratios: dict[str, dict[str, float]] = _dd(dict)
        for s in splits:
            buy_ratios[s["market_code"]][s["buy_timestamp"]] = float(s["ratio"])

        for mc, ratio_map in buy_ratios.items():
            all_txs = conn.execute(
                """
                SELECT t.type, t.quantity, t.timestamp
                FROM transactions t
                JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
                WHERE pa.market_code = ?
                  AND t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
                  AND t.quantity IS NOT NULL
                ORDER BY t.timestamp ASC
            """,
                (mc,),
            ).fetchall()

            split_qty_remaining = 0.0
            current_ratio = 1.0
            current_start = ""
            periods: list[tuple[str, str, float]] = []

            for tx in all_txs:
                tx_date = tx["timestamp"][:10]
                if tx["type"] == "INVESTMENT_BUY":
                    qty = float(tx["quantity"])
                    r = ratio_map.get(tx_date, 0)
                    if r > 0:
                        if split_qty_remaining <= 0:
                            current_start = tx_date
                            current_ratio = r
                        elif current_ratio != r:
                            periods.append((current_start, tx_date, current_ratio))
                            current_start = tx_date
                            current_ratio = r
                        split_qty_remaining += qty
                elif tx["type"] == "INVESTMENT_SELL":
                    qty = float(tx["quantity"])
                    if split_qty_remaining > 0:
                        deducted = min(split_qty_remaining, qty)
                        split_qty_remaining -= deducted
                        if split_qty_remaining <= 0:
                            periods.append((current_start, tx_date, current_ratio))
                            split_qty_remaining = 0

            if split_qty_remaining > 0 and current_start:
                periods.append((current_start, "9999-12-31", current_ratio))

            if periods:
                split_periods[mc] = periods

    # Use monthly steps for spans > 2 years, weekly otherwise
    span_days = (end - start).days
    interval = _td(days=30) if span_days > 730 else _td(days=7)

    dates: list[str] = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += interval

    for date_str in dates:
        positions = get_net_positions_as_of(conn, date_str + "T23:59:59", include_inactive=True)
        pos_map = {p["market_code"]: p["net_quantity"] for p in positions if p["net_quantity"] > 0}
        for a in assets:
            code = a["market_code"]
            qty = pos_map.get(code, 0)
            if qty <= 0:
                continue
            price = price_as_of(code, date_str)
            estimated = False
            if price is None:
                price = first_price.get(code)
                estimated = price is not None
            if price is None:
                continue
            value = round(qty * price, 2)
            # Apply stock split adjustment if date falls within a split period
            if code in split_periods:
                for sp_start, sp_end, sp_ratio in split_periods[code]:
                    if sp_start <= date_str < sp_end:
                        value = round(value * sp_ratio, 2)
                        break
            point = {"date": date_str, "value": value}
            if estimated:
                point["estimated"] = True
            by_asset[code].append(point)

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
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (MarketAssetNotFound, PriceError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{price_id}", response_model=PriceResponse)
async def get_price(price_id: int):
    try:
        return get(price_id)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{price_id}", response_model=PriceResponse)
async def update_price(price_id: int, body: PriceCreate):
    try:
        return update(price_id, body)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (PriceAlreadyExists, MarketAssetNotFound, PriceError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/{price_id}", status_code=204)
async def delete_price(price_id: int):
    try:
        delete(price_id)
    except PriceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
