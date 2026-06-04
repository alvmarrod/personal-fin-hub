import logging
from datetime import date, datetime, time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from db import queries as q
from db.connection import get_db

logger = logging.getLogger(__name__)

_JOB_PREFIX = "schedule_"
_scheduler: BackgroundScheduler | None = None


def reset_scheduler() -> None:
    """Test helper: shut down and clear the module-level scheduler."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def _job_id(schedule_id: int) -> str:
    return f"{_JOB_PREFIX}{schedule_id}"


def _parse_schedule_id(job_id: str) -> int | None:
    if job_id.startswith(_JOB_PREFIX):
        return int(job_id[len(_JOB_PREFIX):])
    return None


def _make_trigger(sch: dict) -> DateTrigger | CronTrigger | None:
    ptype = sch["periodicity_type"]
    start = sch["start_date"]
    if isinstance(start, str):
        start = date.fromisoformat(start)

    if ptype == "ONE_OFF":
        if start < date.today():
            return None
        return DateTrigger(run_date=datetime.combine(start, time.min))

    if ptype == "DAILY":
        return CronTrigger.from_crontab("0 0 * * *")
    if ptype == "WEEKLY":
        return CronTrigger.from_crontab(f"0 0 * * {start.isoweekday() % 7}")
    if ptype == "MONTHLY":
        return CronTrigger.from_crontab(f"0 0 {start.day} * *")
    if ptype == "QUARTERLY":
        return CronTrigger.from_crontab(f"0 0 {start.day} */3 *")
    if ptype == "ANNUALLY":
        return CronTrigger.from_crontab(f"0 0 {start.day} {start.month} *")
    if ptype == "CUSTOM":
        cron = sch.get("custom_cron")
        if not cron:
            logger.warning("Schedule %s has CUSTOM type but no custom_cron", sch["id"])
            return None
        return CronTrigger.from_crontab(cron)

    return None


def _register_job(sched: BackgroundScheduler, sch: dict) -> None:
    jid = _job_id(sch["id"])
    trigger = _make_trigger(sch)
    if trigger is None:
        return
    sched.add_job(
        execute_schedule,
        trigger=trigger,
        id=jid,
        name=sch.get("description", f"Schedule {sch['id']}"),
        args=[sch["id"]],
        replace_existing=True,
        misfire_grace_time=300,
    )


def init_scheduler() -> None:
    sched = get_scheduler()
    conn = get_db()
    schedules = q.get_all_schedules(conn)
    for sch in schedules:
        _register_job(sched, sch)

    if sched.get_jobs():
        sched.start()
        logger.info("Scheduler started with %d jobs", len(sched.get_jobs()))
    else:
        logger.info("No schedules to schedule, scheduler idle")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shut down")


def sync_schedule(schedule_id: int) -> None:
    sched = get_scheduler()
    conn = get_db()
    sch = q.get_schedule(conn, schedule_id)
    if sch is None:
        logger.warning("Schedule %s not found for sync", schedule_id)
        return
    _register_job(sched, sch)
    if not sched.running:
        sched.start()


def remove_schedule(schedule_id: int) -> None:
    sched = get_scheduler()
    jid = _job_id(schedule_id)
    if sched.get_job(jid):
        sched.remove_job(jid)


def _clone_tx(schedule_id: int) -> int | None:
    conn = get_db()
    try:
        sch = q.get_schedule(conn, schedule_id)
        if sch is None:
            logger.warning("Schedule %s not found for execution", schedule_id)
            return None

        now = date.today()
        if sch["end_date"]:
            end = sch["end_date"]
            if isinstance(end, str):
                end = date.fromisoformat(end)
            if now > end:
                logger.info("Schedule %s past end_date, removing job", schedule_id)
                remove_schedule(schedule_id)
                return None

        template = q.get_transaction(conn, sch["linked_transaction_id"])
        if template is None:
            logger.warning("Linked transaction %s not found for schedule %s", sch["linked_transaction_id"], schedule_id)
            return None

        ts = datetime.now().isoformat()
        tx_id = q.create_transaction(
            conn,
            timestamp=ts,
            type_=template["type"],
            entity_id=template["entity_id"],
            currency=template["currency"],
            total_value=template["total_value"],
            transaction_category=template.get("transaction_category"),
            portfolio_asset_id=template.get("portfolio_asset_id"),
            quantity=template.get("quantity"),
            unit_price=template.get("unit_price"),
            gross_amount=template.get("gross_amount"),
            net_amount=template.get("net_amount"),
            payment_currency=template.get("payment_currency"),
            fx_rate=template.get("fx_rate"),
            settlement_date=template.get("settlement_date"),
            fiscal_exemption_id=template.get("fiscal_exemption_id"),
            dividend_type=template.get("dividend_type"),
            record_date=template.get("record_date"),
            payment_date=template.get("payment_date"),
            dividend_currency=template.get("dividend_currency"),
            dividend_payment_currency=template.get("dividend_payment_currency"),
            dividend_fx_rate=template.get("dividend_fx_rate"),
            notes=template.get("notes"),
        )

        for fee in q.get_fees_by_transaction(conn, template["id"]):
            q.create_fee(
                conn,
                transaction_id=tx_id,
                fee_type=fee["fee_type"],
                nature=fee["nature"],
                currency=fee["currency"],
                fixed_amount=fee["fixed_amount"],
                percentage=fee["percentage"],
            )

        for tax in q.get_taxes_by_transaction(conn, template["id"]):
            q.create_tax(
                conn,
                transaction_id=tx_id,
                tax_type=tax["tax_type"],
                tax_amount=tax["tax_amount"],
                currency=tax["currency"],
                tax_rate=tax.get("tax_rate"),
            )

        conn.commit()
        logger.info("Cloned transaction %s from schedule %s", tx_id, schedule_id)
        return tx_id
    except Exception:
        conn.rollback()
        raise


def execute_schedule(schedule_id: int) -> None:
    try:
        _clone_tx(schedule_id)
    except Exception as e:
        logger.error("Failed to execute schedule %s: %s", schedule_id, e)
