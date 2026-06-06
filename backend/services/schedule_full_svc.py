from datetime import date, datetime, time

from db.connection import get_db
from db import queries
from models import ScheduleFullCreate, ScheduleFullResponse, TransactionCreate
from scheduler.scheduler import sync_schedule
from services.transaction_svc import FKNotFound, create as create_transaction


class SnapshotConstraintError(Exception):
    pass


def _check_snapshot_constraint(conn, body: ScheduleFullCreate) -> None:
    if body.schedule.entity_id is None or body.schedule.currency is None:
        return
    snapshot = queries.get_latest_snapshot(conn, body.schedule.entity_id, body.schedule.currency)
    if snapshot is None:
        return
    sd = body.schedule.start_date
    if hasattr(sd, 'isoformat'):
        sd_iso = sd.isoformat()
    else:
        sd_iso = str(sd)
    snap_ts = snapshot["timestamp"]
    snap_date = snap_ts[:10] if isinstance(snap_ts, str) else str(snap_ts)[:10]
    if sd_iso <= snap_date:
        raise SnapshotConstraintError(
            f"Schedule start_date {sd_iso} is not after latest balance snapshot "
            f"{snap_ts} for entity {body.schedule.entity_id} / {body.schedule.currency}"
        )


def create(body: ScheduleFullCreate) -> ScheduleFullResponse:
    conn = get_db()
    try:
        _check_snapshot_constraint(conn, body)
        if body.schedule.entity_id is None or body.schedule.currency is None or body.schedule.type is None:
            raise FKNotFound("Schedule full requires entity_id, currency, and type")
        
        # Only create initial transaction if start_date is today
        tx = None
        if body.schedule.start_date == date.today():
            tx_body = TransactionCreate(
                timestamp=datetime.combine(body.schedule.start_date, time.min),
                type=body.schedule.type,
                entity_id=body.schedule.entity_id,
                currency=body.schedule.currency,
                total_value=body.schedule.total_value,
                notes=body.schedule.notes,
            )
            tx = create_transaction(tx_body, conn=conn)
        
        schedule_id = queries.create_schedule(
            conn,
            description=body.schedule.description,
            start_date=body.schedule.start_date.isoformat(),
            periodicity_type=body.schedule.periodicity_type.value,
            end_date=body.schedule.end_date.isoformat() if body.schedule.end_date else None,
            custom_cron=body.schedule.custom_cron,
            entity_id=body.schedule.entity_id,
            currency=body.schedule.currency,
            type_=body.schedule.type.value,
            total_value=body.schedule.total_value,
            notes=body.schedule.notes,
        )
        conn.commit()
        sync_schedule(schedule_id)
        schedule_row = queries.get_schedule(conn, schedule_id)
        from models import ScheduleResponse
        from models.enums import PeriodicityType, TransactionType
        schedule_resp = ScheduleResponse(
            id=schedule_row["id"],
            description=schedule_row["description"],
            start_date=schedule_row["start_date"],
            end_date=schedule_row["end_date"],
            periodicity_type=PeriodicityType(schedule_row["periodicity_type"]),
            custom_cron=schedule_row["custom_cron"],
            entity_id=schedule_row["entity_id"],
            currency=schedule_row["currency"],
            type=TransactionType(schedule_row["type"]) if schedule_row["type"] else None,
            total_value=schedule_row["total_value"],
            notes=schedule_row["notes"],
        )
        return ScheduleFullResponse(schedule=schedule_resp, transaction=tx)
    except FKNotFound:
        conn.rollback()
        raise
    except SnapshotConstraintError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
