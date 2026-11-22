from fastapi import APIRouter, HTTPException, Query

from models import (
    DebtCancelBody,
    DebtCreate,
    DebtDetail,
    DebtDirection,
    DebtPaymentBody,
    DebtPlanEntry,
    DebtPlanImport,
    DebtRateBody,
    DebtResponse,
    DebtSettleBody,
    DebtStatus,
    DebtSummary,
    DebtUpdate,
)
from services import debt_svc

router = APIRouter(prefix="/debt", tags=["debt"])


def _raise(error: Exception) -> None:
    if isinstance(error, debt_svc.DebtNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("", response_model=list[DebtResponse])
async def list_debts(
    direction: DebtDirection | None = None,
    status: DebtStatus | None = None,
):
    return debt_svc.list_debts(
        direction=direction.value if direction else None,
        status=status.value if status else None,
    )


@router.get("/summary", response_model=DebtSummary)
async def debt_summary(display_currency: str = Query(...)):
    return debt_svc.summary(display_currency)


@router.get("/counterparties", response_model=list[str])
async def debt_counterparties():
    return debt_svc.counterparties()


@router.post("", response_model=DebtDetail, status_code=201)
async def create_debt(body: DebtCreate):
    try:
        return debt_svc.create(body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.get("/{debt_id}", response_model=DebtDetail)
async def get_debt(debt_id: int):
    try:
        return debt_svc.get(debt_id)
    except debt_svc.DebtError as e:
        _raise(e)


@router.put("/{debt_id}", response_model=DebtDetail)
async def update_debt(debt_id: int, body: DebtUpdate):
    try:
        return debt_svc.update(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.delete("/{debt_id}", status_code=204)
async def delete_debt(debt_id: int):
    try:
        debt_svc.delete(debt_id)
    except debt_svc.DebtError as e:
        _raise(e)


@router.post("/{debt_id}/payments", response_model=DebtDetail, status_code=201)
async def record_payment(debt_id: int, body: DebtPaymentBody):
    try:
        return debt_svc.record_payment(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.delete("/{debt_id}/payments/{payment_id}", response_model=DebtDetail)
async def delete_payment(debt_id: int, payment_id: int):
    try:
        return debt_svc.delete_payment(debt_id, payment_id)
    except debt_svc.DebtError as e:
        _raise(e)


@router.post("/{debt_id}/rates", response_model=DebtDetail, status_code=201)
async def add_rate(debt_id: int, body: DebtRateBody):
    try:
        return debt_svc.add_rate(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.post("/{debt_id}/settle", response_model=DebtDetail)
async def settle_debt(debt_id: int, body: DebtSettleBody):
    try:
        return debt_svc.settle(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.post("/{debt_id}/cancel", response_model=DebtDetail)
async def cancel_debt(debt_id: int, body: DebtCancelBody):
    try:
        return debt_svc.cancel(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)


@router.get("/{debt_id}/plan", response_model=list[DebtPlanEntry])
async def get_plan(debt_id: int):
    try:
        return debt_svc.get_plan(debt_id)
    except debt_svc.DebtError as e:
        _raise(e)


@router.put("/{debt_id}/plan", response_model=list[DebtPlanEntry])
async def import_plan(debt_id: int, body: DebtPlanImport):
    try:
        return debt_svc.import_plan(debt_id, body)
    except debt_svc.DebtError as e:
        _raise(e)
