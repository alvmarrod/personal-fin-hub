from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models import (
    AllocationLine,
    CashFlowSummary,
    DashboardSummary,
    DividendLine,
    FeeTaxSummary,
    HistoricalValuePoint,
    HoldingByEntityLine,
    HoldingLine,
    IncomeBySourceLine,
    PerformanceSummary,
    RealizedGainLine,
)
from services.analytics_svc import (
    AnalyticsError,
    get_asset_allocation,
    get_cash_balances,
    get_cash_by_currency_history_svc,
    get_cash_flow,
    get_dashboard,
    get_dividends,
    get_fees_taxes,
    get_historical_values,
    get_holdings,
    get_holdings_by_entity,
    get_income_by_source,
    get_performance_summary,
    get_realized_gains,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(display_currency: str = Query("USD", description="Display currency for all values")):
    return get_dashboard(display_currency)


@router.get("/holdings", response_model=list[HoldingLine])
async def holdings():
    return get_holdings()


@router.get("/allocation", response_model=list[AllocationLine])
async def allocation(
    dimension: str = Query("layer", description="Group by: layer, asset_type, currency, asset_class, entity"),
    display_currency: str = Query(None, description="Display currency for all values"),
):
    try:
        return get_asset_allocation(dimension, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/holdings-by-entity", response_model=list[HoldingByEntityLine])
async def holdings_by_entity(
    display_currency: str = Query(None, description="Display currency for all values"),
):
    return get_holdings_by_entity(display_currency)


@router.get("/income-by-source", response_model=list[IncomeBySourceLine])
async def income_by_source(
    group_by: str = Query("month", description="Group by: day, week, month, quarter, year"),
    start_date: Optional[str] = Query(None, description="ISO date start (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO date end (inclusive)"),
):
    try:
        return get_income_by_source(group_by, start_date, end_date)
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


@router.get("/performance", response_model=PerformanceSummary)
async def performance():
    return get_performance_summary()


@router.get("/realized-gains", response_model=list[RealizedGainLine])
async def realized_gains():
    return get_realized_gains()


@router.get("/historical", response_model=list[HistoricalValuePoint])
async def historical(
    start_date: str = Query(..., description="ISO date start (inclusive)"),
    end_date: str = Query(..., description="ISO date end (inclusive)"),
    interval: str = Query("month", description="Step: day, week, month, quarter, year"),
    entity_id: int | None = Query(None, description="Filter by entity ID"),
    display_currency: str = Query(None, description="Display currency for all values"),
):
    try:
        return get_historical_values(start_date, end_date, interval, entity_id, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cash-balances")
async def cash_balances():
    return get_cash_balances()


@router.get("/cash-by-currency-history")
async def cash_by_currency_history(
    start_date: str = Query(..., description="ISO date start (inclusive)"),
    end_date: str = Query(..., description="ISO date end (inclusive)"),
    interval: str = Query("month", description="Step: day, week, month, quarter, year"),
):
    return get_cash_by_currency_history_svc(start_date, end_date, interval)
