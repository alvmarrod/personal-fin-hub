from datetime import date

from fastapi import APIRouter, HTTPException, Query

from models import StrategyDrift, StrategyHistory, StrategySetBody, StrategyTargetSet
from services.analytics_svc import AnalyticsError
from services.strategy_svc import (
    StrategyExists,
    StrategyNotFound,
    create,
    delete,
    drift,
    history,
    list_sets,
    replace,
)

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("", response_model=list[StrategyTargetSet])
async def list_strategy_sets():
    return list_sets()


@router.post("", response_model=StrategyTargetSet, status_code=201)
async def create_strategy_set(body: StrategySetBody):
    try:
        return create(body)
    except StrategyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/drift", response_model=StrategyDrift)
async def strategy_drift(display_currency: str | None = Query(default=None)):
    return drift(display_currency)


@router.get("/history", response_model=StrategyHistory)
async def strategy_history(
    start_date: str = Query(...),
    end_date: str = Query(...),
    interval: str = Query("month"),
    display_currency: str | None = Query(default=None),
):
    try:
        return history(start_date, end_date, interval, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{effective_from}", response_model=StrategyTargetSet)
async def replace_strategy_set(effective_from: date, body: StrategySetBody):
    try:
        return replace(effective_from, body)
    except StrategyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{effective_from}", status_code=204)
async def delete_strategy_set(effective_from: date):
    try:
        delete(effective_from)
    except StrategyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
