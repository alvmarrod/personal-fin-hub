from fastapi import APIRouter, HTTPException

from models import TransferCreate, TransferResponse
from services.transfer_svc import TransferError, create
from services.transaction_svc import FKNotFound

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferResponse, status_code=201)
async def create_transfer(body: TransferCreate):
    try:
        return create(body)
    except FKNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TransferError as e:
        raise HTTPException(status_code=422, detail=str(e))
