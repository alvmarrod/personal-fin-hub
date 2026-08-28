from datetime import date
from typing import Literal

from db import queries
from db.connection import get_db
from models import PortfolioAssetCreate, PortfolioAssetResponse, PortfolioAssetTransaction
from models.enums import (
    DcaStatus,
    DistributionType,
    InvestmentTransactionCategory,
    Layer,
    TrackingMode,
    TransactionType,
)


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
    _sync_manual_value_ledger(conn, body, asset_id)
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
    open_asset_ids = {h.portfolio_asset_id for h in holdings if h.net_quantity > 0}

    _attach_transactions(conn, assets, open_asset_ids)

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
    _sync_manual_value_ledger(conn, body, asset_id)
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


def _attach_transactions(conn, assets: list[PortfolioAssetResponse], open_asset_ids: set[int]) -> None:
    """Attach each asset's buy transactions (per broker) for open positions.

    Buys are read from the shared buy/sell query (entity name included). Only
    assets with a remaining position (net quantity > 0) carry the list; fully
    sold assets carry an empty list. The frontend uses this to expand a row and
    show how the position is split across brokers.
    """
    if not open_asset_ids:
        return
    from db.analytics_queries import get_buy_sell_transactions

    buy_rows = get_buy_sell_transactions(conn)
    by_asset: dict[int, list[PortfolioAssetTransaction]] = {}
    for r in buy_rows:
        if r["type"] != "INVESTMENT_BUY":
            continue
        if r["portfolio_asset_id"] not in open_asset_ids:
            continue
        by_asset.setdefault(r["portfolio_asset_id"], []).append(
            PortfolioAssetTransaction(
                id=r["transaction_id"],
                timestamp=r["timestamp"],
                type=TransactionType(r["type"]),
                investment_transaction_category=InvestmentTransactionCategory(r["investment_transaction_category"])
                if r.get("investment_transaction_category")
                else None,
                entity_id=r["entity_id"],
                entity_name=r.get("entity_name"),
                quantity=r["quantity"],
                unit_price=r["unit_price"],
                total_value=r["total_value"],
                currency=r["currency"],
                payment_currency=r.get("payment_currency"),
                fx_rate=r.get("fx_rate"),
            )
        )
    for asset in assets:
        buys = by_asset.get(asset.id, [])
        buys.sort(key=lambda b: b.timestamp.replace(tzinfo=None))
        asset.transactions = buys


def _sync_manual_value_ledger(conn, body: PortfolioAssetCreate, asset_id: int) -> None:
    """Record a manual value snapshot into the manual_values ledger (UC-45).

    Writes only when the asset is manual-tracked and the payload carries a value.
    Effective date defaults to today for backdated corrections. Same-day revalue
    replaces that date's row (UPSERT).
    """
    if body.tracking_mode != TrackingMode.MANUAL or body.current_value_manual is None:
        return
    effective_date = (body.effective_date or date.today()).isoformat()
    queries.upsert_manual_value(conn, asset_id, body.current_value_manual, effective_date, body.notes)


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
