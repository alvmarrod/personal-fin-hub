from fastapi import APIRouter, HTTPException, Query

from models import TransactionFeeCreate, TransactionFeeResponse
from services.transaction_fee_svc import (
    TransactionFeeError,
    TransactionFeeNotFound,
    TransactionNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/transaction-fees", tags=["transaction_fees"])


@router.get("", response_model=list[TransactionFeeResponse])
async def list_fees(transaction_id: int | None = Query(None)):
    return list_all(transaction_id)


@router.post("", response_model=TransactionFeeResponse, status_code=201)
async def create_fee(body: TransactionFeeCreate):
    try:
        return create(body)
    except TransactionNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{fee_id}", response_model=TransactionFeeResponse)
async def get_fee(fee_id: int):
    try:
        return get(fee_id)
    except TransactionFeeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{fee_id}", response_model=TransactionFeeResponse)
async def update_fee(fee_id: int, body: TransactionFeeCreate):
    try:
        return update(fee_id, body)
    except TransactionFeeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TransactionNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{fee_id}", status_code=204)
async def delete_fee(fee_id: int):
    try:
        delete(fee_id)
    except TransactionFeeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
