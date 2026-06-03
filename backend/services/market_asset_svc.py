import sqlite3

from db.connection import get_db
from db import queries
from models import MarketAsset
from models.enums import AssetClass, AssetType


class MarketAssetError(Exception):
    pass


class MarketAssetNotFound(MarketAssetError):
    pass


class MarketAssetAlreadyExists(MarketAssetError):
    pass


class CurrencyNotFound(MarketAssetError):
    pass


def create(body: MarketAsset) -> MarketAsset:
    conn = get_db()
    if queries.get_market_asset(conn, body.market_code):
        raise MarketAssetAlreadyExists(
            f"Market asset '{body.market_code}' already exists"
        )
    if not queries.code_exists(conn, body.currency_code):
        raise CurrencyNotFound(
            f"Currency '{body.currency_code}' not found. Register it first via POST /currencies"
        )
    try:
        queries.create_market_asset(
            conn,
            market_code=body.market_code,
            ticker=body.ticker,
            asset_type=body.asset_type.value,
            asset_class=body.asset_class.value if body.asset_class else None,
            currency_code=body.currency_code,
            name=body.name,
            description=body.description,
            exchange=body.exchange,
        )
    except sqlite3.IntegrityError as e:
        raise MarketAssetAlreadyExists(str(e))
    conn.commit()
    return body


def get(market_code: str) -> MarketAsset:
    conn = get_db()
    row = queries.get_market_asset(conn, market_code)
    if row is None:
        raise MarketAssetNotFound(f"Market asset '{market_code}' not found")
    return MarketAsset(
        market_code=row["market_code"],
        ticker=row["ticker"],
        asset_type=AssetType(row["asset_type"]),
        asset_class=AssetClass(row["asset_class"]) if row["asset_class"] else None,
        currency_code=row["currency_code"],
        name=row["name"],
        description=row["description"],
        exchange=row["exchange"],
    )


def list_all() -> list[MarketAsset]:
    conn = get_db()
    rows = queries.get_all_market_assets(conn)
    return [
        MarketAsset(
            market_code=r["market_code"],
            ticker=r["ticker"],
            asset_type=AssetType(r["asset_type"]),
            asset_class=AssetClass(r["asset_class"]) if r["asset_class"] else None,
            currency_code=r["currency_code"],
            name=r["name"],
            description=r["description"],
            exchange=r["exchange"],
        )
        for r in rows
    ]


def update(market_code: str, body: MarketAsset) -> MarketAsset:
    if body.market_code != market_code:
        raise MarketAssetError(
            f"Path market_code '{market_code}' does not match body market_code '{body.market_code}'"
        )
    conn = get_db()
    existing = queries.get_market_asset(conn, market_code)
    if existing is None:
        raise MarketAssetNotFound(f"Market asset '{market_code}' not found")
    if not queries.code_exists(conn, body.currency_code):
        raise CurrencyNotFound(
            f"Currency '{body.currency_code}' not found. Register it first via POST /currencies"
        )
    queries.update_market_asset(
        conn,
        market_code=body.market_code,
        ticker=body.ticker,
        asset_type=body.asset_type.value,
        asset_class=body.asset_class.value if body.asset_class else None,
        currency_code=body.currency_code,
        name=body.name,
        description=body.description,
        exchange=body.exchange,
    )
    conn.commit()
    return body


def delete(market_code: str) -> None:
    conn = get_db()
    existing = queries.get_market_asset(conn, market_code)
    if existing is None:
        raise MarketAssetNotFound(f"Market asset '{market_code}' not found")
    queries.delete_market_asset(conn, market_code)
    conn.commit()
