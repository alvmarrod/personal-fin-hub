import sqlite3

from db.connection import get_db
from db import queries
from models import ScheduleFullCreate, ScheduleFullResponse
from scheduler.scheduler import sync_schedule
from services.transaction_svc import FKNotFound, create as create_transaction


def create(body: ScheduleFullCreate) -> ScheduleFullResponse:
    conn = get_db()
    try:
        tx = create_transaction(body.transaction, conn=conn)
        schedule_id = queries.create_schedule(
            conn,
            description=body.schedule.description,
            start_date=body.schedule.start_date.isoformat(),
            periodicity_type=body.schedule.periodicity_type.value,
            end_date=body.schedule.end_date.isoformat() if body.schedule.end_date else None,
            custom_cron=body.schedule.custom_cron,
            linked_transaction_id=tx.id,
        )
        conn.commit()
        sync_schedule(schedule_id)
        schedule_row = queries.get_schedule(conn, schedule_id)
        from models import ScheduleResponse
        from models.enums import PeriodicityType
        schedule_resp = ScheduleResponse(
            id=schedule_row["id"],
            description=schedule_row["description"],
            start_date=schedule_row["start_date"],
            end_date=schedule_row["end_date"],
            periodicity_type=PeriodicityType(schedule_row["periodicity_type"]),
            custom_cron=schedule_row["custom_cron"],
            linked_transaction_id=schedule_row["linked_transaction_id"],
        )
        return ScheduleFullResponse(schedule=schedule_resp, transaction=tx)
    except FKNotFound:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
