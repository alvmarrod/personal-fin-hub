from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models import (
    CurrencyPair,
    CurrencyRateResponse,
    CurrencyHoldingHistory,
    RateChartResponse,
)
from services.currency_svc import (
    CurrencyError,
    PairNotFound,
    get_codes,
    get_pairs,
    get_rate,
    get_history,
    sync_rates,
    get_historical_holdings,
    get_rate_chart_data,
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


@router.post("/sync")
async def sync_currency_rates():
    try:
        return sync_rates()
    except CurrencyError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/holdings", response_model=CurrencyHoldingHistory)
async def holdings(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    display_currency: str = Query("USD", description="Currency to convert all values into"),
):
    return get_historical_holdings(start_date, end_date, display_currency)


@router.get("/rate-chart", response_model=RateChartResponse)
async def rate_chart(
    base_currency: str = Query("USD", description="Base currency for the chart"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    return get_rate_chart_data(base_currency, start_date, end_date)
