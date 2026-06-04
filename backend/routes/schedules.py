from fastapi import APIRouter, HTTPException

from models import ScheduleCreate, ScheduleResponse
from services.schedule_svc import (
    ScheduleError,
    ScheduleNotFound,
    TransactionNotFound,
    create,
    list_all,
    get,
    update,
    delete,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules():
    return list_all()


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(body: ScheduleCreate):
    try:
        return create(body)
    except (TransactionNotFound, ScheduleError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: int):
    try:
        return get(schedule_id)
    except ScheduleNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: int, body: ScheduleCreate):
    try:
        return update(schedule_id, body)
    except ScheduleNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (TransactionNotFound, ScheduleError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int):
    try:
        delete(schedule_id)
    except ScheduleNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
