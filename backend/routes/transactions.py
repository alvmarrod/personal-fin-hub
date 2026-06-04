from fastapi import APIRouter, HTTPException

from models import BatchCreate, BatchResponse, FullTransactionCreate, FullTransactionResponse, TransactionCreate, TransactionResponse
from services.transaction_batch_svc import BatchError, create as batch_create
from services.transaction_full_svc import create as compound_create
from services.transaction_svc import (
    FKNotFound,
    TransactionError,
    TransactionNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionResponse])
async def list_transactions():
    return list_all()


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_transaction(body: TransactionCreate):
    try:
        return create(body)
    except FKNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/full", response_model=FullTransactionResponse, status_code=201)
async def create_full_transaction(body: FullTransactionCreate):
    try:
        return compound_create(body)
    except FKNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=BatchResponse, status_code=201)
async def create_batch(body: BatchCreate):
    try:
        return batch_create(body)
    except FKNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BatchError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{tx_id}", response_model=TransactionResponse)
async def get_transaction(tx_id: int):
    try:
        return get(tx_id)
    except TransactionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{tx_id}", response_model=TransactionResponse)
async def update_transaction(tx_id: int, body: TransactionCreate):
    try:
        return update(tx_id, body)
    except TransactionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FKNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tx_id}", status_code=204)
async def delete_transaction(tx_id: int):
    try:
        delete(tx_id)
    except TransactionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
