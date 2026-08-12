from fastapi import APIRouter, HTTPException, Query

from models import ManualValueCreate, ManualValueResponse, PortfolioAssetCreate, PortfolioAssetResponse
from services.portfolio_asset_svc import (
    MarketAssetNotFound,
    PortfolioAssetHasDependents,
    PortfolioAssetNotFound,
    create,
    delete,
    get,
    list_all,
    update,
)

router = APIRouter(prefix="/portfolio-assets", tags=["portfolio-assets"])


@router.get("", response_model=list[PortfolioAssetResponse])
async def list_portfolio_assets(display_currency: str | None = Query(default=None)):
    return list_all(display_currency)


@router.post("", response_model=PortfolioAssetResponse, status_code=201)
async def create_portfolio_asset(body: PortfolioAssetCreate):
    try:
        return create(body)
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{asset_id}", response_model=PortfolioAssetResponse)
async def get_portfolio_asset(asset_id: int):
    try:
        return get(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{asset_id}", response_model=PortfolioAssetResponse)
async def update_portfolio_asset(asset_id: int, body: PortfolioAssetCreate):
    try:
        return update(asset_id, body)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/{asset_id}", status_code=204)
async def delete_portfolio_asset(asset_id: int):
    try:
        delete(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PortfolioAssetHasDependents as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{asset_id}/manual-values", response_model=list[ManualValueResponse])
async def list_manual_values(asset_id: int):
    from db import queries
    from db.connection import get_db
    from services.portfolio_asset_svc import PortfolioAssetNotFound, get

    conn = get_db()
    try:
        get(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return queries.get_manual_values(conn, asset_id)


@router.post("/{asset_id}/manual-values", response_model=ManualValueResponse, status_code=201)
async def create_manual_value(asset_id: int, body: ManualValueCreate):
    from db import queries
    from db.connection import get_db
    from services.portfolio_asset_svc import PortfolioAssetNotFound, get

    conn = get_db()
    try:
        get(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    val_row = queries.upsert_manual_value(conn, asset_id, body.value, body.effective_date.isoformat(), body.notes)
    conn.commit()
    return val_row


@router.delete("/{asset_id}/manual-values/{value_id}", status_code=204)
async def delete_manual_value(asset_id: int, value_id: int):
    from db import queries
    from db.connection import get_db

    conn = get_db()
    row = conn.execute(
        "SELECT id FROM manual_values WHERE id = ? AND portfolio_asset_id = ?",
        (value_id, asset_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Manual value not found")
    queries.delete_manual_value(conn, value_id)
    conn.commit()
