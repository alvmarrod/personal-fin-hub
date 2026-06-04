from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models import (
    AllocationLine,
    CashFlowSummary,
    DashboardSummary,
    DividendLine,
    FeeTaxSummary,
    HoldingLine,
)
from services.analytics_svc import (
    AnalyticsError,
    get_asset_allocation,
    get_cash_flow,
    get_dashboard,
    get_dividends,
    get_fees_taxes,
    get_holdings,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard():
    return get_dashboard()


@router.get("/holdings", response_model=list[HoldingLine])
async def holdings():
    return get_holdings()


@router.get("/allocation", response_model=list[AllocationLine])
async def allocation(dimension: str = Query("layer", description="Group by: layer, asset_type, currency")):
    try:
        return get_asset_allocation(dimension)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cash-flow", response_model=CashFlowSummary)
async def cash_flow(
    group_by: str = Query("month", description="Group by: day, week, month, quarter, year"),
    start_date: Optional[str] = Query(None, description="ISO date start (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO date end (inclusive)"),
):
    try:
        return get_cash_flow(group_by, start_date, end_date)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dividends", response_model=list[DividendLine])
async def dividends(
    start_date: Optional[str] = Query(None, description="ISO date start (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO date end (inclusive)"),
):
    return get_dividends(start_date, end_date)


@router.get("/fees-taxes", response_model=FeeTaxSummary)
async def fees_taxes(
    start_date: Optional[str] = Query(None, description="ISO date start (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO date end (inclusive)"),
):
    return get_fees_taxes(start_date, end_date)
