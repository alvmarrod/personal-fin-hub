from fastapi import APIRouter, HTTPException

from models import FiscalPeriodCreate, FiscalPeriodResponse
from services.fiscal_period_svc import (
    FiscalPeriodError,
    FiscalPeriodNotFound,
    FiscalPeriodOverlap,
    create,
    delete,
    get,
    list_all,
    update,
)

router = APIRouter(prefix="/fiscal-periods", tags=["fiscal-periods"])


@router.get("", response_model=list[FiscalPeriodResponse])
async def list_fiscal_periods():
    return list_all()


@router.post("", response_model=FiscalPeriodResponse, status_code=201)
async def create_fiscal_period(body: FiscalPeriodCreate):
    try:
        return create(body)
    except FiscalPeriodOverlap as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except FiscalPeriodError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{period_id}", response_model=FiscalPeriodResponse)
async def get_fiscal_period(period_id: int):
    try:
        return get(period_id)
    except FiscalPeriodNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{period_id}", response_model=FiscalPeriodResponse)
async def update_fiscal_period(period_id: int, body: FiscalPeriodCreate):
    try:
        return update(period_id, body)
    except FiscalPeriodNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FiscalPeriodOverlap as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/{period_id}", status_code=204)
async def delete_fiscal_period(period_id: int):
    try:
        delete(period_id)
    except FiscalPeriodNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
