import logging
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from db import queries as q
from db.connection import get_db

logger = logging.getLogger(__name__)

_JOB_PREFIX = "schedule_"
_CATCHUP_TAG_PREFIX = "[schedule:"
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
        return int(job_id[len(_JOB_PREFIX) :])
    return None


# ---------------------------------------------------------------------------
# Scheduler state persistence
# ---------------------------------------------------------------------------


def _set_state(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO scheduler_state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def _get_state(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM scheduler_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _save_shutdown_timestamp() -> None:
    conn = get_db()
    try:
        _set_state(conn, "last_shutdown_at", datetime.now().isoformat())
    finally:
        conn.close()


def _get_last_shutdown(conn) -> datetime | None:
    raw = _get_state(conn, "last_shutdown_at")
    if raw is None:
        return None
    return datetime.fromisoformat(raw)


# ---------------------------------------------------------------------------
# Catch-up computation
# ---------------------------------------------------------------------------


def _next_month_day(d: date, day: int) -> date:
    """Return the next month that contains *day*, clamped to month end."""
    if d.month == 12:
        next_m, next_y = 1, d.year + 1
    else:
        next_m, next_y = d.month + 1, d.year
    max_day = monthrange(next_y, next_m)[1]
    return date(next_y, next_m, min(day, max_day))


def _compute_fire_dates(sch: dict, since: date, until: date) -> list[date]:
    """Compute all intended fire dates for *sch* in [since, until].

    Respects end_date: if set, fires are not generated beyond it.
    """
    start = sch["start_date"]
    if isinstance(start, str):
        start = date.fromisoformat(start)

    end = sch.get("end_date")
    if end is not None:
        if isinstance(end, str):
            end = date.fromisoformat(end)
        if start > end:
            return []
        until = min(until, end)

    ptype = sch["periodicity_type"]

    if ptype == "ONE_OFF":
        if since <= start <= until:
            return [start]
        return []

    fires: list[date] = []
    current = start

    if ptype == "DAILY":
        while current <= until:
            if current >= since:
                fires.append(current)
            current += timedelta(days=1)

    elif ptype == "WEEKLY":
        while current <= until:
            if current >= since:
                fires.append(current)
            current += timedelta(days=7)

    elif ptype == "MONTHLY":
        day = start.day
        while current <= until:
            if current >= since:
                fires.append(current)
            current = _next_month_day(current, day)

    elif ptype == "QUARTERLY":
        day = start.day
        while current <= until:
            if current >= since:
                fires.append(current)
            m = current.month + 3
            y = current.year
            while m > 12:
                m -= 12
                y += 1
            max_d = monthrange(y, m)[1]
            current = date(y, m, min(day, max_d))

    elif ptype == "ANNUALLY":
        day, month = start.day, start.month
        while current <= until:
            if current >= since:
                fires.append(current)
            current = date(current.year + 1, month, min(day, monthrange(current.year + 1, month)[1]))

    else:
        logger.warning("Catch-up not supported for periodicity %s, skipping", ptype)

    return fires


def _catchup_tag(schedule_id: int) -> str:
    return f"[schedule:{schedule_id}]"


def _has_catchup_for_date(conn, schedule_id: int, fire_date: date) -> bool:
    """Idempotency check: did we already create a catch-up tx for this date?"""
    tag = _catchup_tag(schedule_id)
    date_prefix = fire_date.isoformat()
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE notes LIKE ? AND timestamp LIKE ? LIMIT 1",
        (f"%{tag}%", f"{date_prefix}%"),
    ).fetchone()
    return row is not None


def _create_catchup_tx(conn, sch: dict, fire_date: date) -> int | None:
    """Create a single backdated transaction for a missed fire."""
    schedule_id = sch["id"]

    if _has_catchup_for_date(conn, schedule_id, fire_date):
        return None

    if sch["entity_id"] is not None and q.get_entity(conn, sch["entity_id"]) is None:
        logger.warning(
            "Catch-up: entity %s soft-deleted, skipping schedule %s for %s",
            sch["entity_id"],
            schedule_id,
            fire_date,
        )
        return None

    if not sch.get("type") or sch.get("entity_id") is None or sch.get("currency") is None:
        logger.warning(
            "Catch-up: schedule %s missing required fields, skipping",
            schedule_id,
        )
        return None

    ts = datetime.combine(fire_date, time.min).isoformat()
    base_notes = sch.get("notes") or ""
    tag = _catchup_tag(schedule_id)
    notes = f"{base_notes} {tag}" if base_notes else tag

    tx_id = q.create_transaction(
        conn,
        timestamp=ts,
        type_=sch["type"],
        entity_id=sch["entity_id"],
        currency=sch["currency"],
        total_value=sch["total_value"],
        notes=notes,
    )
    logger.info(
        "Catch-up: created tx %s for schedule %s (fire date %s)",
        tx_id,
        schedule_id,
        fire_date,
    )
    return tx_id


def catch_up_missed_fires() -> None:
    """Backfill transactions for fires missed while the app was down.

    Called synchronously before init_scheduler() on startup.
    Uses the persisted last_shutdown_at timestamp to compute the window.
    """
    conn = get_db()
    try:
        last_shutdown = _get_last_shutdown(conn)
        now = datetime.now()

        schedules = q.get_all_schedules(conn)

        if last_shutdown is None:
            if not schedules:
                logger.info("Catch-up: no previous shutdown timestamp and no schedules, skipping")
                return
            earliest = min(
                (date.fromisoformat(s["start_date"]) if isinstance(s["start_date"], str) else s["start_date"])
                for s in schedules
            )
            if earliest >= now.date():
                logger.info("Catch-up: all schedules start in the future, skipping")
                return
            logger.info(
                "Catch-up: no previous shutdown timestamp, bootstrapping from earliest schedule start_date %s",
                earliest,
            )
            since_date = earliest
        else:
            since_date = last_shutdown.date()

        until_date = now.date()

        total_created = 0
        for sch in schedules:
            sch_start = sch["start_date"]
            if isinstance(sch_start, str):
                sch_start = date.fromisoformat(sch_start)
            # Use the earlier of last_shutdown or schedule's own start_date,
            # so newly-created schedules with past start_dates are still caught up
            sch_since = min(since_date, sch_start) if last_shutdown else sch_start
            fire_dates = _compute_fire_dates(sch, sch_since, until_date)
            for fd in fire_dates:
                tx_id = _create_catchup_tx(conn, sch, fd)
                if tx_id is not None:
                    total_created += 1
                    try:
                        from services.transaction_svc import _recalculate_adjustments

                        _recalculate_adjustments(
                            conn,
                            sch["entity_id"],
                            sch["currency"],
                            datetime.combine(fd, time.min).isoformat(),
                        )
                    except Exception:
                        logger.warning(
                            "Catch-up: adjustment recalc failed for schedule %s date %s",
                            sch["id"],
                            fd,
                        )

        if total_created > 0:
            conn.commit()
            logger.info("Catch-up complete: created %d transaction(s)", total_created)
        else:
            logger.info("Catch-up: no missed fires found")
    except Exception:
        conn.rollback()
        logger.exception("Catch-up failed")
    finally:
        conn.close()


def catch_up_single_schedule(schedule_id: int) -> None:
    """Execute missed fires for a single schedule from its start_date to now."""
    conn = get_db()
    try:
        sch = q.get_schedule(conn, schedule_id)
        if sch is None:
            return

        start = sch["start_date"]
        if isinstance(start, str):
            start = date.fromisoformat(start)
        now = datetime.now()

        if start >= now.date():
            return

        fire_dates = _compute_fire_dates(sch, start, now.date())
        total = 0
        for fd in fire_dates:
            tx_id = _create_catchup_tx(conn, sch, fd)
            if tx_id is not None:
                total += 1
                try:
                    from services.transaction_svc import _recalculate_adjustments

                    _recalculate_adjustments(
                        conn,
                        sch["entity_id"],
                        sch["currency"],
                        datetime.combine(fd, time.min).isoformat(),
                    )
                except Exception:
                    logger.warning(
                        "Single catch-up: adjustment recalc failed for schedule %s date %s",
                        schedule_id,
                        fd,
                    )

        if total > 0:
            conn.commit()
            logger.info("Single catch-up: created %d transaction(s) for schedule %s", total, schedule_id)
    except Exception:
        conn.rollback()
        logger.exception("Single catch-up failed for schedule %s", schedule_id)
    finally:
        conn.close()


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
    try:
        _save_shutdown_timestamp()
    except Exception:
        logger.warning("Could not persist scheduler shutdown timestamp")


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

        if sch["entity_id"] is not None and q.get_entity(conn, sch["entity_id"]) is None:
            logger.warning(
                "Entity %s is soft-deleted, skipping schedule %s",
                sch["entity_id"],
                schedule_id,
            )
            return None

        if not sch.get("type") or sch.get("entity_id") is None or sch.get("currency") is None:
            logger.warning(
                "Schedule %s missing required embedded fields, skipping",
                schedule_id,
            )
            return None

        ts = datetime.now().isoformat()
        base_notes = sch.get("notes") or ""
        tag = _catchup_tag(schedule_id)
        notes = f"{base_notes} {tag}" if base_notes else tag

        type_ = sch.get("type")
        entity_id = sch.get("entity_id")
        currency = sch.get("currency")
        assert type_ is not None and entity_id is not None and currency is not None
        tx_id = q.create_transaction(
            conn,
            timestamp=ts,
            type_=type_,
            entity_id=entity_id,
            currency=currency,
            total_value=sch.get("total_value"),
            notes=notes,
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
