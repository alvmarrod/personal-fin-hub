from typing import Literal

from db import queries
from db.connection import get_db
from models import PortfolioAssetCreate, PortfolioAssetResponse
from models.enums import DcaStatus, DistributionType, Layer, TrackingMode


class PortfolioAssetError(Exception):
    pass


class PortfolioAssetNotFound(PortfolioAssetError):
    pass


class MarketAssetNotFound(PortfolioAssetError):
    pass


class PortfolioAssetHasDependents(PortfolioAssetError):
    pass


def create(body: PortfolioAssetCreate) -> PortfolioAssetResponse:
    conn = get_db()
    if not queries.get_market_asset(conn, body.market_code):
        raise MarketAssetNotFound(
            f"Market asset '{body.market_code}' not found. Register it first via POST /market-assets"
        )
    asset_id = queries.create_portfolio_asset(
        conn,
        market_code=body.market_code,
        distribution_type=body.distribution_type.value if body.distribution_type else None,
        dca_status=body.dca_status.value if body.dca_status else None,
        layer=body.layer.value if body.layer else None,
        tactic=body.tactic,
        desired_weight=body.desired_weight,
        ter=body.ter,
        tracking_mode=body.tracking_mode.value,
        current_value_manual=body.current_value_manual,
        is_active=body.is_active,
        closing_date=body.closing_date.isoformat() if body.closing_date else None,
        notes=body.notes,
    )
    conn.commit()
    return PortfolioAssetResponse(
        id=asset_id,
        market_code=body.market_code,
        distribution_type=body.distribution_type,
        dca_status=body.dca_status,
        layer=body.layer,
        tactic=body.tactic,
        desired_weight=body.desired_weight,
        ter=body.ter,
        tracking_mode=body.tracking_mode,
        current_value_manual=body.current_value_manual,
        is_active=body.is_active,
        closing_date=body.closing_date,
        notes=body.notes,
    )


def get(asset_id: int) -> PortfolioAssetResponse:
    conn = get_db()
    row = queries.get_portfolio_asset(conn, asset_id)
    if row is None:
        raise PortfolioAssetNotFound(f"Portfolio asset {asset_id} not found")
    return _row_to_response(row)


def list_all(display_currency: str | None = None) -> list[PortfolioAssetResponse]:
    conn = get_db()
    rows = queries.get_all_portfolio_assets(conn)
    assets = [_row_to_response(r) for r in rows]

    from services.analytics_svc import get_holdings

    holdings = get_holdings(conn)
    holding_map: dict[int, tuple[float | None, float | None, str]] = {}
    for h in holdings:
        holding_map[h.portfolio_asset_id] = (h.current_value, h.unrealized_pl_pct, h.currency_code)
    price_meta_map: dict[int, tuple[Literal["market-api", "transaction-fallback", "manual", "none"], str | None]] = {
        h.portfolio_asset_id: (h.price_source, h.price_as_of) for h in holdings
    }

    if display_currency:
        from services.currency_svc import PairNotFound, get_rate

        rate_cache: dict[str, float] = {}
        needed = {cur for _, _, cur in holding_map.values() if cur != display_currency}
        for cur in needed:
            try:
                rate_cache[cur] = get_rate(cur, display_currency).rate
            except PairNotFound:
                pass

        for a in assets:
            data = holding_map.get(a.id)
            if data:
                cv, pl_pct, src = data
                a.unrealized_pl_pct = pl_pct
                if cv is not None:
                    if src != display_currency and src in rate_cache:
                        a.current_value = round(cv * rate_cache[src], 4)
                    elif src == display_currency:
                        a.current_value = cv
    else:
        for a in assets:
            data = holding_map.get(a.id)
            if data:
                a.current_value = data[0]
                a.unrealized_pl_pct = data[1]

    for a in assets:
        meta = price_meta_map.get(a.id)
        if meta:
            a.price_source = meta[0]
            a.price_as_of = meta[1]

    return assets


def update(asset_id: int, body: PortfolioAssetCreate) -> PortfolioAssetResponse:
    conn = get_db()
    existing = queries.get_portfolio_asset(conn, asset_id)
    if existing is None:
        raise PortfolioAssetNotFound(f"Portfolio asset {asset_id} not found")
    if not queries.get_market_asset(conn, body.market_code):
        raise MarketAssetNotFound(
            f"Market asset '{body.market_code}' not found. Register it first via POST /market-assets"
        )
    queries.update_portfolio_asset(
        conn,
        asset_id,
        market_code=body.market_code,
        distribution_type=body.distribution_type.value if body.distribution_type else None,
        dca_status=body.dca_status.value if body.dca_status else None,
        layer=body.layer.value if body.layer else None,
        tactic=body.tactic,
        desired_weight=body.desired_weight,
        ter=body.ter,
        tracking_mode=body.tracking_mode.value,
        current_value_manual=body.current_value_manual,
        is_active=body.is_active,
        closing_date=body.closing_date.isoformat() if body.closing_date else None,
        notes=body.notes,
    )
    conn.commit()
    return PortfolioAssetResponse(
        id=asset_id,
        market_code=body.market_code,
        distribution_type=body.distribution_type,
        dca_status=body.dca_status,
        layer=body.layer,
        tactic=body.tactic,
        desired_weight=body.desired_weight,
        ter=body.ter,
        tracking_mode=body.tracking_mode,
        current_value_manual=body.current_value_manual,
        is_active=body.is_active,
        closing_date=body.closing_date,
        notes=body.notes,
    )


def delete(asset_id: int) -> None:
    conn = get_db()
    existing = queries.get_portfolio_asset(conn, asset_id)
    if existing is None:
        raise PortfolioAssetNotFound(f"Portfolio asset {asset_id} not found")
    if queries.portfolio_asset_has_dependents(conn, asset_id):
        raise PortfolioAssetHasDependents(f"Portfolio asset {asset_id} has transactions referencing it")
    queries.delete_portfolio_asset(conn, asset_id)
    conn.commit()


def _row_to_response(row: dict) -> PortfolioAssetResponse:
    return PortfolioAssetResponse(
        id=row["id"],
        market_code=row["market_code"],
        distribution_type=DistributionType(row["distribution_type"]) if row["distribution_type"] else None,
        dca_status=DcaStatus(row["dca_status"]) if row["dca_status"] else None,
        layer=Layer(row["layer"]) if row["layer"] else None,
        tactic=bool(row["tactic"]),
        desired_weight=row["desired_weight"],
        ter=row["ter"],
        tracking_mode=TrackingMode(row["tracking_mode"]) if row["tracking_mode"] else TrackingMode.AUTO,
        current_value_manual=row["current_value_manual"],
        is_active=bool(row["is_active"]),
        closing_date=row["closing_date"],
        notes=row["notes"],
    )
