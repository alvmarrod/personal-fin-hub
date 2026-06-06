from fastapi import APIRouter, HTTPException

from models import FiscalExemptionCreate, FiscalExemptionResponse
from services.fiscal_exemption_svc import (
    FiscalExemptionError,
    FiscalExemptionHasDependents,
    FiscalExemptionNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/fiscal-exemptions", tags=["fiscal-exemptions"])


@router.get("", response_model=list[FiscalExemptionResponse])
async def list_fiscal_exemptions():
    return list_all()


@router.post("", response_model=FiscalExemptionResponse, status_code=201)
async def create_fiscal_exemption(body: FiscalExemptionCreate):
    try:
        return create(body)
    except FiscalExemptionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{exemption_id}", response_model=FiscalExemptionResponse)
async def get_fiscal_exemption(exemption_id: int):
    try:
        return get(exemption_id)
    except FiscalExemptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{exemption_id}", response_model=FiscalExemptionResponse)
async def update_fiscal_exemption(exemption_id: int, body: FiscalExemptionCreate):
    try:
        return update(exemption_id, body)
    except FiscalExemptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{exemption_id}", status_code=204)
async def delete_fiscal_exemption(exemption_id: int):
    try:
        delete(exemption_id)
    except FiscalExemptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FiscalExemptionHasDependents as e:
        raise HTTPException(status_code=409, detail=str(e))
