from fastapi import APIRouter, HTTPException, Query

from models import TransactionTaxCreate, TransactionTaxResponse
from services.transaction_tax_svc import (
    TransactionTaxError,
    TransactionTaxNotFound,
    TransactionNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/transaction-taxes", tags=["transaction_taxes"])


@router.get("", response_model=list[TransactionTaxResponse])
async def list_taxes(transaction_id: int | None = Query(None)):
    return list_all(transaction_id)


@router.post("", response_model=TransactionTaxResponse, status_code=201)
async def create_tax(body: TransactionTaxCreate):
    try:
        return create(body)
    except TransactionNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tax_id}", response_model=TransactionTaxResponse)
async def get_tax(tax_id: int):
    try:
        return get(tax_id)
    except TransactionTaxNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{tax_id}", response_model=TransactionTaxResponse)
async def update_tax(tax_id: int, body: TransactionTaxCreate):
    try:
        return update(tax_id, body)
    except TransactionTaxNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TransactionNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tax_id}", status_code=204)
async def delete_tax(tax_id: int):
    try:
        delete(tax_id)
    except TransactionTaxNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
