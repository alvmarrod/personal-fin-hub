from fastapi import APIRouter, HTTPException, Query

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
