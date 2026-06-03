from fastapi import APIRouter, HTTPException

from models import MarketAsset
from services.market_asset_svc import (
    CurrencyNotFound,
    MarketAssetAlreadyExists,
    MarketAssetError,
    MarketAssetNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/market-assets", tags=["market-assets"])


@router.get("", response_model=list[MarketAsset])
async def list_market_assets():
    return list_all()


@router.post("", response_model=MarketAsset, status_code=201)
async def create_market_asset(body: MarketAsset):
    try:
        return create(body)
    except MarketAssetAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (CurrencyNotFound, MarketAssetError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{market_code}", response_model=MarketAsset)
async def get_market_asset(market_code: str):
    try:
        return get(market_code)
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{market_code}", response_model=MarketAsset)
async def update_market_asset(market_code: str, body: MarketAsset):
    try:
        return update(market_code, body)
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (CurrencyNotFound, MarketAssetError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{market_code}", status_code=204)
async def delete_market_asset(market_code: str):
    try:
        delete(market_code)
    except MarketAssetNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
