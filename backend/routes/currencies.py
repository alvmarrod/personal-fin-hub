from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models import (
    CurrencyCodeCreate,
    CurrencyPair,
    CurrencyRateBulkUpsert,
    CurrencyRateCreate,
    CurrencyRateResponse,
)
from services.currency_svc import (
    CurrencyError,
    PairNotFound,
    RateNotFound,
    ReversePairExists,
    register_code,
    get_codes,
    get_pairs,
    create_rate,
    get_rate,
    get_history,
    update_rates,
    delete_pair,
    delete_code,
)

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[str])
async def list_codes():
    return get_codes()


@router.post("", response_model=CurrencyRateResponse, status_code=201)
async def register(body: CurrencyCodeCreate):
    try:
        return register_code(body.code)
    except CurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/rates", response_model=list[CurrencyPair])
async def list_pairs(code: Optional[str] = Query(None)):
    return get_pairs(code)


@router.post("/rates", response_model=CurrencyRateResponse, status_code=201)
async def create_rate_entry(body: CurrencyRateCreate):
    try:
        return create_rate(
            code=body.code,
            base_code=body.base_code,
            rate=body.rate,
            timestamp=body.timestamp,
        )
    except ReversePairExists as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/rates/{code}/{base_code}", response_model=CurrencyRateResponse)
async def get_latest_rate(
    code: str,
    base_code: str,
    at: Optional[datetime] = Query(None),
):
    try:
        return get_rate(code, base_code, at)
    except PairNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/rates/{code}/{base_code}/history",
    response_model=list[CurrencyRateResponse],
)
async def get_rate_history(code: str, base_code: str):
    try:
        return get_history(code, base_code)
    except PairNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/rates/{code}/{base_code}", response_model=list[CurrencyRateResponse])
async def bulk_update_rates(code: str, base_code: str, body: CurrencyRateBulkUpsert):
    try:
        return update_rates(code, base_code, body.timestamps, body.rates)
    except ReversePairExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (PairNotFound, RateNotFound) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rates/{code}/{base_code}", status_code=204)
async def delete_rates(code: str, base_code: str):
    try:
        deleted = delete_pair(code, base_code)
        if not deleted:
            raise PairNotFound(f"Pair ({code}, {base_code}) not found")
    except PairNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{code}", status_code=204)
async def delete_currency_code(code: str):
    try:
        delete_code(code)
    except CurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
