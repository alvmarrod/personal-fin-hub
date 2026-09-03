from fastapi import APIRouter, HTTPException, Query

from models import (
    AllocationLine,
    CashFlowSummaryWithRates,
    CashFlowTransactionsResponse,
    DashboardSummary,
    DividendLine,
    FeeTaxSummary,
    HistoricalValuePoint,
    HoldingByEntityLine,
    HoldingLine,
    IncomeBySourceWithRates,
    PerformanceSummary,
    RealizedGainLine,
    TaxablePnlSummary,
    TaxablePnlSummaryExtended,
)
from services.analytics_svc import (
    AnalyticsError,
    get_asset_allocation,
    get_cash_balances,
    get_cash_by_currency_history_svc,
    get_cash_flow,
    get_cash_flow_txns,
    get_dashboard,
    get_dividends,
    get_fees_taxes,
    get_historical_values,
    get_holdings,
    get_holdings_by_entity,
    get_income_by_source,
    get_performance_summary,
    get_projected_income,
    get_realized_gains,
    get_taxable_pnl,
    get_taxable_pnl_extended,
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
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/holdings-by-entity", response_model=list[HoldingByEntityLine])
async def holdings_by_entity(
    display_currency: str = Query(None, description="Display currency for all values"),
):
    return get_holdings_by_entity(display_currency)


@router.get("/income-by-source", response_model=IncomeBySourceWithRates)
async def income_by_source(
    group_by: str = Query("month", description="Group by: day, week, month, quarter, year"),
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
    display_currency: str | None = Query(None, description="Display currency for all values"),
):
    try:
        return get_income_by_source(group_by, start_date, end_date, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/cash-flow", response_model=CashFlowSummaryWithRates)
async def cash_flow(
    group_by: str = Query("month", description="Group by: day, week, month, quarter, year"),
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
    display_currency: str | None = Query(None, description="Display currency for all values"),
):
    try:
        return get_cash_flow(group_by, start_date, end_date, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/cash-flow/transactions", response_model=CashFlowTransactionsResponse)
async def cash_flow_transactions(
    group_by: str = Query("month", description="Group by: day, week, month, quarter, year"),
    period: str = Query(..., description="Period key (e.g. 2025-01)"),
    type: str = Query(..., description="Transaction type"),
    category: str | None = Query(None, description="Category (null for MONEY_OUT)"),
    currency: str = Query(..., description="Currency code"),
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
    display_currency: str | None = Query(None, description="Display currency for converted per-transaction amounts"),
):
    try:
        return get_cash_flow_txns(group_by, period, type, category, currency, start_date, end_date, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/projected-income", response_model=IncomeBySourceWithRates)
async def projected_income(
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
    display_currency: str | None = Query(None, description="Display currency for all values"),
):
    try:
        return get_projected_income(start_date, end_date, display_currency)
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/dividends", response_model=list[DividendLine])
async def dividends(
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
    display_currency: str | None = Query(None, description="Currency for the converted per-line totals"),
):
    return get_dividends(start_date, end_date, display_currency)


@router.get("/fees-taxes", response_model=FeeTaxSummary)
async def fees_taxes(
    start_date: str | None = Query(None, description="ISO date start (inclusive)"),
    end_date: str | None = Query(None, description="ISO date end (inclusive)"),
):
    return get_fees_taxes(start_date, end_date)


@router.get("/performance", response_model=PerformanceSummary)
async def performance(
    display_currency: str = Query("USD", description="Display currency for all values"),
    locale: str = Query("", description="Locale used to infer the default fiscal rule"),
):
    return get_performance_summary(display_currency, locale)


@router.get("/realized-gains", response_model=list[RealizedGainLine])
async def realized_gains():
    return get_realized_gains()


@router.get("/taxable-pnl", response_model=TaxablePnlSummary)
async def taxable_pnl(
    display_currency: str = Query("USD", description="Display currency for all values"),
    locale: str = Query("", description="Locale used to infer the default ruleset"),
    ruleset: str = Query("", description="Fiscal ruleset (spain, japan, default, latest, none)"),
):
    return get_taxable_pnl(display_currency, locale, ruleset)


@router.get("/taxable-pnl-extended", response_model=TaxablePnlSummaryExtended)
async def taxable_pnl_extended(
    display_currency: str = Query("USD", description="Display currency for all values"),
    locale: str = Query("", description="Locale used to infer the default ruleset"),
    ruleset: str = Query("", description="Fiscal ruleset (spain, japan, default, latest, none)"),
):
    return get_taxable_pnl_extended(display_currency, locale, ruleset)


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
        raise HTTPException(status_code=400, detail=str(e)) from e


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
