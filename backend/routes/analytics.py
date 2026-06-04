from fastapi import APIRouter, HTTPException, Query

from models import AllocationLine, DashboardSummary, HoldingLine
from services.analytics_svc import AnalyticsError, get_asset_allocation, get_dashboard, get_holdings

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
