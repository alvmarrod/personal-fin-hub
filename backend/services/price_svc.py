import sqlite3

from db.connection import get_db
from db import queries
from models import PriceCreate, PriceResponse


class PriceError(Exception):
    pass


class PriceNotFound(PriceError):
    pass


class PriceAlreadyExists(PriceError):
    pass


class MarketAssetNotFound(PriceError):
    pass


def create(body: PriceCreate) -> PriceResponse:
    conn = get_db()
    if not queries.get_market_asset(conn, body.market_code):
        raise MarketAssetNotFound(
            f"Market asset '{body.market_code}' not found"
        )
    try:
        price_id = queries.create_price(
            conn,
            market_code=body.market_code,
            timestamp=body.timestamp.isoformat() if hasattr(body.timestamp, 'isoformat') else body.timestamp,
            price=body.price,
            provider=body.provider,
        )
    except sqlite3.IntegrityError as e:
        raise PriceAlreadyExists(
            f"Price already exists for market '{body.market_code}' at {body.timestamp}"
        )
    conn.commit()
    return PriceResponse(
        id=price_id,
        market_code=body.market_code,
        timestamp=body.timestamp,
        price=body.price,
        provider=body.provider,
    )


def get(price_id: int) -> PriceResponse:
    conn = get_db()
    row = queries.get_price(conn, price_id)
    if row is None:
        raise PriceNotFound(f"Price {price_id} not found")
    return PriceResponse(
        id=row["id"],
        market_code=row["market_code"],
        timestamp=row["timestamp"],
        price=row["price"],
        provider=row["provider"],
    )


def list_all(market_code: str | None = None) -> list[PriceResponse]:
    conn = get_db()
    if market_code is not None:
        rows = queries.get_prices_by_market(conn, market_code)
    else:
        rows = queries.get_all_prices(conn)
    return [
        PriceResponse(
            id=r["id"],
            market_code=r["market_code"],
            timestamp=r["timestamp"],
            price=r["price"],
            provider=r["provider"],
        )
        for r in rows
    ]


def update(price_id: int, body: PriceCreate) -> PriceResponse:
    conn = get_db()
    existing = queries.get_price(conn, price_id)
    if existing is None:
        raise PriceNotFound(f"Price {price_id} not found")
    if not queries.get_market_asset(conn, body.market_code):
        raise MarketAssetNotFound(
            f"Market asset '{body.market_code}' not found"
        )
    try:
        ok = queries.update_price(
            conn,
            price_id,
            market_code=body.market_code,
            timestamp=body.timestamp.isoformat() if hasattr(body.timestamp, 'isoformat') else body.timestamp,
            price=body.price,
            provider=body.provider,
        )
    except sqlite3.IntegrityError as e:
        raise PriceAlreadyExists(
            f"Price already exists for market '{body.market_code}' at {body.timestamp}"
        )
    if not ok:
        raise PriceNotFound(f"Price {price_id} not found")
    conn.commit()
    return PriceResponse(
        id=price_id,
        market_code=body.market_code,
        timestamp=body.timestamp,
        price=body.price,
        provider=body.provider,
    )


def delete(price_id: int) -> None:
    conn = get_db()
    existing = queries.get_price(conn, price_id)
    if existing is None:
        raise PriceNotFound(f"Price {price_id} not found")
    queries.delete_price(conn, price_id)
    conn.commit()
