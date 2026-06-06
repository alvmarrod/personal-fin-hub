from fastapi import APIRouter, HTTPException, Query

from models import BalanceSnapshotCreate, BalanceSnapshotResponse
from services.balance_snapshot_svc import (
    BalanceSnapshotConflict,
    BalanceSnapshotError,
    BalanceSnapshotNotFound,
    CurrencyNotFound,
    EntityNotFound,
    create,
    delete,
    get,
    list_all,
    update,
)

router = APIRouter(prefix="/balance-snapshots", tags=["balance-snapshots"])


@router.get("", response_model=list[BalanceSnapshotResponse])
async def list_balance_snapshots(
    entity_id: int | None = Query(None),
    currency: str | None = Query(None),
):
    return list_all(entity_id=entity_id, currency=currency)


@router.post("", response_model=BalanceSnapshotResponse, status_code=201)
async def create_balance_snapshot(body: BalanceSnapshotCreate):
    try:
        return create(body)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CurrencyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BalanceSnapshotConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except BalanceSnapshotError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{snapshot_id}", response_model=BalanceSnapshotResponse)
async def get_balance_snapshot(snapshot_id: int):
    try:
        return get(snapshot_id)
    except BalanceSnapshotNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{snapshot_id}", response_model=BalanceSnapshotResponse)
async def update_balance_snapshot(snapshot_id: int, body: BalanceSnapshotCreate):
    try:
        return update(snapshot_id, body)
    except BalanceSnapshotNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CurrencyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BalanceSnapshotError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{snapshot_id}", status_code=204)
async def delete_balance_snapshot(snapshot_id: int):
    try:
        delete(snapshot_id)
    except BalanceSnapshotNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
