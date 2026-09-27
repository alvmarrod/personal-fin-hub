from fastapi import APIRouter, HTTPException

from models import TaxBaseCreate, TaxBaseResponse
from services.tax_catalog_svc import (
    TaxBaseNotFound,
    TaxCatalogError,
    create_tax_base,
    delete_tax_base,
    get_tax_base,
    list_tax_bases,
    update_tax_base,
)

router = APIRouter(prefix="/tax-bases", tags=["tax-bases"])


@router.get("", response_model=list[TaxBaseResponse])
async def list_all():
    return list_tax_bases()


@router.post("", response_model=TaxBaseResponse, status_code=201)
async def create(body: TaxBaseCreate):
    try:
        return create_tax_base(body)
    except TaxCatalogError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{base_id}", response_model=TaxBaseResponse)
async def get(base_id: int):
    try:
        return get_tax_base(base_id)
    except TaxBaseNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{base_id}", response_model=TaxBaseResponse)
async def update(base_id: int, body: TaxBaseCreate):
    try:
        return update_tax_base(base_id, body)
    except TaxBaseNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TaxCatalogError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/{base_id}", status_code=204)
async def delete(base_id: int):
    try:
        delete_tax_base(base_id)
    except TaxBaseNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
