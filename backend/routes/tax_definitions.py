from fastapi import APIRouter, HTTPException

from models import TaxDefinitionCreate, TaxDefinitionResponse
from services.tax_catalog_svc import (
    TaxDefinitionInUse,
    TaxDefinitionNotFound,
    TaxDefinitionSlugTaken,
    create_tax_definition,
    delete_tax_definition,
    get_tax_definition,
    list_tax_definitions,
    update_tax_definition,
)

router = APIRouter(prefix="/tax-definitions", tags=["tax-definitions"])


@router.get("", response_model=list[TaxDefinitionResponse])
async def list_all():
    return list_tax_definitions()


@router.post("", response_model=TaxDefinitionResponse, status_code=201)
async def create(body: TaxDefinitionCreate):
    try:
        return create_tax_definition(body)
    except TaxDefinitionSlugTaken as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{definition_id}", response_model=TaxDefinitionResponse)
async def get(definition_id: int):
    try:
        return get_tax_definition(definition_id)
    except TaxDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{definition_id}", response_model=TaxDefinitionResponse)
async def update(definition_id: int, body: TaxDefinitionCreate):
    try:
        return update_tax_definition(definition_id, body)
    except TaxDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TaxDefinitionSlugTaken as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/{definition_id}", status_code=204)
async def delete(definition_id: int):
    try:
        delete_tax_definition(definition_id)
    except TaxDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TaxDefinitionInUse as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
