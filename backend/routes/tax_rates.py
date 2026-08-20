from fastapi import APIRouter, HTTPException

from models import TaxRateCreate, TaxRateResponse
from services.tax_rate_svc import (
    TaxRateError,
    TaxRateNotFound,
    create,
    delete,
    get,
    list_all,
    update,
)

router = APIRouter(prefix="/tax-rates", tags=["tax-rates"])


@router.get("", response_model=list[TaxRateResponse])
async def list_tax_rates(
    ruleset_key: str | None = None,
    category: str | None = None,
    year_start: int | None = None,
):
    return list_all(ruleset_key, category, year_start)


@router.post("", response_model=TaxRateResponse, status_code=201)
async def create_tax_rate(body: TaxRateCreate):
    try:
        return create(body)
    except TaxRateError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{rate_id}", response_model=TaxRateResponse)
async def get_tax_rate(rate_id: int):
    try:
        return get(rate_id)
    except TaxRateNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{rate_id}", response_model=TaxRateResponse)
async def update_tax_rate(rate_id: int, body: TaxRateCreate):
    try:
        return update(rate_id, body)
    except TaxRateNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{rate_id}", status_code=204)
async def delete_tax_rate(rate_id: int):
    try:
        delete(rate_id)
    except TaxRateNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
