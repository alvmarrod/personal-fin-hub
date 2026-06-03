from fastapi import APIRouter, HTTPException

from models import PortfolioAssetCreate, PortfolioAssetResponse
from services.portfolio_asset_svc import (
    MarketAssetNotFound,
    PortfolioAssetError,
    PortfolioAssetNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/portfolio-assets", tags=["portfolio-assets"])


@router.get("", response_model=list[PortfolioAssetResponse])
async def list_portfolio_assets():
    return list_all()


@router.post("", response_model=PortfolioAssetResponse, status_code=201)
async def create_portfolio_asset(body: PortfolioAssetCreate):
    try:
        return create(body)
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{asset_id}", response_model=PortfolioAssetResponse)
async def get_portfolio_asset(asset_id: int):
    try:
        return get(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{asset_id}", response_model=PortfolioAssetResponse)
async def update_portfolio_asset(asset_id: int, body: PortfolioAssetCreate):
    try:
        return update(asset_id, body)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{asset_id}", status_code=204)
async def delete_portfolio_asset(asset_id: int):
    try:
        delete(asset_id)
    except PortfolioAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
