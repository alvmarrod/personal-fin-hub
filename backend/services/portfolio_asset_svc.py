from db.connection import get_db
from db import queries
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
        purchase_date=body.purchase_date.isoformat() if body.purchase_date else None,
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
        purchase_date=body.purchase_date,
        notes=body.notes,
    )


def get(asset_id: int) -> PortfolioAssetResponse:
    conn = get_db()
    row = queries.get_portfolio_asset(conn, asset_id)
    if row is None:
        raise PortfolioAssetNotFound(f"Portfolio asset {asset_id} not found")
    return _row_to_response(row)


def list_all() -> list[PortfolioAssetResponse]:
    conn = get_db()
    rows = queries.get_all_portfolio_assets(conn)
    return [_row_to_response(r) for r in rows]


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
        purchase_date=body.purchase_date.isoformat() if body.purchase_date else None,
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
        purchase_date=body.purchase_date,
        notes=body.notes,
    )


def delete(asset_id: int) -> None:
    conn = get_db()
    existing = queries.get_portfolio_asset(conn, asset_id)
    if existing is None:
        raise PortfolioAssetNotFound(f"Portfolio asset {asset_id} not found")
    if queries.portfolio_asset_has_dependents(conn, asset_id):
        raise PortfolioAssetHasDependents(
            f"Portfolio asset {asset_id} has transactions referencing it"
        )
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
        purchase_date=row["purchase_date"],
        notes=row["notes"],
    )
