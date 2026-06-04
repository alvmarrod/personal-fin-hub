import sqlite3

from db.connection import get_db
from db import queries
from models import ScheduleCreate, ScheduleResponse
from models.enums import PeriodicityType


class ScheduleError(Exception):
    pass


class ScheduleNotFound(ScheduleError):
    pass


class TransactionNotFound(ScheduleError):
    pass


def create(body: ScheduleCreate) -> ScheduleResponse:
    conn = get_db()
    if body.linked_transaction_id is not None:
        if not queries.get_transaction(conn, body.linked_transaction_id):
            raise TransactionNotFound(
                f"Transaction {body.linked_transaction_id} not found"
            )
    schedule_id = queries.create_schedule(
        conn,
        description=body.description,
        start_date=body.start_date.isoformat(),
        periodicity_type=body.periodicity_type.value,
        end_date=body.end_date.isoformat() if body.end_date else None,
        custom_cron=body.custom_cron,
        linked_transaction_id=body.linked_transaction_id,
    )
    conn.commit()
    return ScheduleResponse(
        id=schedule_id,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        periodicity_type=body.periodicity_type,
        custom_cron=body.custom_cron,
        linked_transaction_id=body.linked_transaction_id,
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
        linked_transaction_id=row["linked_transaction_id"],
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
            linked_transaction_id=r["linked_transaction_id"],
        )
        for r in rows
    ]


def update(schedule_id: int, body: ScheduleCreate) -> ScheduleResponse:
    conn = get_db()
    existing = queries.get_schedule(conn, schedule_id)
    if existing is None:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    if body.linked_transaction_id is not None:
        if not queries.get_transaction(conn, body.linked_transaction_id):
            raise TransactionNotFound(
                f"Transaction {body.linked_transaction_id} not found"
            )
    ok = queries.update_schedule(
        conn,
        schedule_id,
        description=body.description,
        start_date=body.start_date.isoformat(),
        periodicity_type=body.periodicity_type.value,
        end_date=body.end_date.isoformat() if body.end_date else None,
        custom_cron=body.custom_cron,
        linked_transaction_id=body.linked_transaction_id,
    )
    if not ok:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    conn.commit()
    return ScheduleResponse(
        id=schedule_id,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        periodicity_type=body.periodicity_type,
        custom_cron=body.custom_cron,
        linked_transaction_id=body.linked_transaction_id,
    )


def delete(schedule_id: int) -> None:
    conn = get_db()
    existing = queries.get_schedule(conn, schedule_id)
    if existing is None:
        raise ScheduleNotFound(f"Schedule {schedule_id} not found")
    queries.delete_schedule(conn, schedule_id)
    conn.commit()
