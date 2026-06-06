import sqlite3

from db.connection import get_db
from db import queries
from models import ScheduleCreate, ScheduleResponse
from models.enums import PeriodicityType, TransactionType
from scheduler.scheduler import remove_schedule, sync_schedule


class ScheduleError(Exception):
    pass


class ScheduleNotFound(ScheduleError):
    pass


class EntityNotFound(ScheduleError):
    pass


class CurrencyNotFound(ScheduleError):
    pass


def create(body: ScheduleCreate) -> ScheduleResponse:
    conn = get_db()
    if body.entity_id is not None:
        if not queries.get_entity(conn, body.entity_id):
            raise EntityNotFound(f"Entity {body.entity_id} not found")
    if body.currency is not None:
        if not queries.code_exists(conn, body.currency):
            raise CurrencyNotFound(f"Currency '{body.currency}' not found")
    schedule_id = queries.create_schedule(
        conn,
        description=body.description,
        start_date=body.start_date.isoformat(),
        periodicity_type=body.periodicity_type.value,
        end_date=body.end_date.isoformat() if body.end_date else None,
        custom_cron=body.custom_cron,
        entity_id=body.entity_id,
        currency=body.currency,
        type_=body.type.value if body.type else None,
        total_value=body.total_value,
        notes=body.notes,
    )
    conn.commit()
    sync_schedule(schedule_id)
    return ScheduleResponse(
        id=schedule_id,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        periodicity_type=body.periodicity_type,
        custom_cron=body.custom_cron,
        entity_id=body.entity_id,
        currency=body.currency,
        type=body.type,
        total_value=body.total_value,
        notes=body.notes,
    )


def get(schedule_id: int) -> ScheduleResponse:
    conn = get_db()
    row = queries.get_schedule(conn, schedule_id)
    if row is None:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    return ScheduleResponse(
        id=row["id"],
        description=row["description"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        periodicity_type=PeriodicityType(row["periodicity_type"]),
        custom_cron=row["custom_cron"],
        entity_id=row["entity_id"],
        currency=row["currency"],
        type=TransactionType(row["type"]) if row["type"] else None,
        total_value=row["total_value"],
        notes=row["notes"],
    )


def list_all() -> list[ScheduleResponse]:
    conn = get_db()
    rows = queries.get_all_schedules(conn)
    return [
        ScheduleResponse(
            id=r["id"],
            description=r["description"],
            start_date=r["start_date"],
            end_date=r["end_date"],
            periodicity_type=PeriodicityType(r["periodicity_type"]),
            custom_cron=r["custom_cron"],
            entity_id=r["entity_id"],
            currency=r["currency"],
            type=TransactionType(r["type"]) if r["type"] else None,
            total_value=r["total_value"],
            notes=r["notes"],
        )
        for r in rows
    ]


def update(schedule_id: int, body: ScheduleCreate) -> ScheduleResponse:
    conn = get_db()
    existing = queries.get_schedule(conn, schedule_id)
    if existing is None:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    if body.entity_id is not None:
        if not queries.get_entity(conn, body.entity_id):
            raise EntityNotFound(f"Entity {body.entity_id} not found")
    if body.currency is not None:
        if not queries.code_exists(conn, body.currency):
            raise CurrencyNotFound(f"Currency '{body.currency}' not found")
    ok = queries.update_schedule(
        conn,
        schedule_id,
        description=body.description,
        start_date=body.start_date.isoformat(),
        periodicity_type=body.periodicity_type.value,
        end_date=body.end_date.isoformat() if body.end_date else None,
        custom_cron=body.custom_cron,
        entity_id=body.entity_id,
        currency=body.currency,
        type_=body.type.value if body.type else None,
        total_value=body.total_value,
        notes=body.notes,
    )
    if not ok:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    conn.commit()
    sync_schedule(schedule_id)
    return ScheduleResponse(
        id=schedule_id,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        periodicity_type=body.periodicity_type,
        custom_cron=body.custom_cron,
        entity_id=body.entity_id,
        currency=body.currency,
        type=body.type,
        total_value=body.total_value,
        notes=body.notes,
    )


def delete(schedule_id: int) -> None:
    conn = get_db()
    existing = queries.get_schedule(conn, schedule_id)
    if existing is None:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    queries.delete_schedule(conn, schedule_id)
    conn.commit()
    remove_schedule(schedule_id)
