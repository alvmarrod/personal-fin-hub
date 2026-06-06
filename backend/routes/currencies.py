from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models import CurrencyPair, CurrencyRateResponse
from services.currency_svc import (
    PairNotFound,
    get_codes,
    get_pairs,
    get_rate,
    get_history,
)

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[str])
async def list_codes():
    return get_codes()


@router.get("/rates", response_model=list[CurrencyPair])
async def list_pairs(code: Optional[str] = Query(None)):
    return get_pairs(code)


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
