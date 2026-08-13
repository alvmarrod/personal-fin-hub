import logging
from calendar import monthrange
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from db import queries as q
from db.connection import ProfileScopedConnection, get_db
from services.backup_svc import backup_cron_parts, backup_enabled, backup_timezone, run_daily_backup

logger = logging.getLogger(__name__)

_JOB_PREFIX = "schedule_"
_CATCHUP_TAG_PREFIX = "[schedule:"
_scheduler: BackgroundScheduler | None = None


@contextmanager
def _scoped_profile(conn, profile_id):
    """Temporarily bind *conn* to *profile_id* so generated rows are stamped.

    The scheduler runs outside the request context (no contextvar), so the
    connection starts unscoped. Scoping it per-schedule ensures the created
    transaction, schedule_occurrence and balance-adjustment rows carry the
    schedule's profile_id. Plain sqlite3.Connection objects (tests only)
    are left unscoped.
    """
    previous = getattr(conn, "profile_id", None)
    if isinstance(conn, ProfileScopedConnection):
        conn.profile_id = profile_id
    try:
        yield conn
    finally:
        if isinstance(conn, ProfileScopedConnection):
            conn.profile_id = previous


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
        _set_state(conn, "last_shutdown_at", datetime.now(UTC).isoformat())
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
    """Check schedule_occurrences to see if this fire date was already materialized."""
    return q.get_schedule_occurrence(conn, schedule_id, fire_date.isoformat()) is not None


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

    with _scoped_profile(conn, sch.get("profile_id")):
        tx_id = q.create_transaction(
            conn,
            timestamp=ts,
            type_=sch["type"],
            entity_id=sch["entity_id"],
            currency=sch["currency"],
            total_value=sch["total_value"],
            notes=notes,
            portfolio_asset_id=sch.get("portfolio_asset_id"),
        )

        if tx_id and sch.get("portfolio_asset_id") and sch["type"] in ("INVESTMENT_BUY", "INVESTMENT_SELL"):
            from models import TransactionCreate
            from services.transaction_svc import _resolve_investment_fields

            tx_row = q.get_transaction(conn, tx_id)
            if tx_row:
                body = TransactionCreate(
                    timestamp=tx_row["timestamp"],
                    type=tx_row["type"],
                    entity_id=tx_row["entity_id"],
                    portfolio_asset_id=tx_row["portfolio_asset_id"],
                    quantity=tx_row["quantity"],
                    unit_price=tx_row["unit_price"],
                    total_value=tx_row["total_value"],
                    currency=tx_row["currency"],
                )
                qty, up, tv = _resolve_investment_fields(body)
                if qty is not None or up is not None:
                    conn.execute(
                        "UPDATE transactions SET quantity = ?, unit_price = ?, total_value = ? WHERE id = ?",
                        (qty, up, tv, tx_id),
                    )
                    conn.commit()

        logger.info(
            "Catch-up: created tx %s for schedule %s (fire date %s)",
            tx_id,
            schedule_id,
            fire_date,
        )
        if tx_id:
            q.insert_schedule_occurrence(conn, schedule_id, fire_date.isoformat(), tx_id)
        return tx_id


def catch_up_missed_fires() -> None:
    """Backfill transactions for fires missed while the app was down.

    Called synchronously before init_scheduler() on startup.
    Uses the persisted last_shutdown_at timestamp to compute the window.
    """
    conn = get_db()
    try:
        last_shutdown = _get_last_shutdown(conn)
        now = datetime.now(UTC)

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
            with _scoped_profile(conn, sch.get("profile_id")):
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
        now = datetime.now(UTC)

        if start >= now.date():
            return

        fire_dates = _compute_fire_dates(sch, start, now.date())
        total = 0
        with _scoped_profile(conn, sch.get("profile_id")):
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


def _run_price_sync() -> None:
    """Full paced price sync (UC-46)."""
    from services.config import config
    from services.market_sync_svc import sync_prices

    try:
        result = sync_prices(
            full=True,
            pace=config.market_api_sync_cron_pace_seconds,
        )
        logger.info("Price sync (cron): synced=%s", result.get("synced", 0))
    except Exception:
        logger.exception("Price sync (cron) failed")


def _register_price_sync_job(sched: BackgroundScheduler) -> None:
    from services.config import config

    hours = config.market_api_sync_cron_hours
    if not hours:
        return
    hour_spec = ",".join(str(int(h)) for h in hours)
    sched.add_job(
        _run_price_sync,
        trigger=CronTrigger(hour=hour_spec, minute=0, timezone="UTC"),
        id="price_sync",
        name="Price sync (full refresh)",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )


def init_scheduler() -> None:
    sched = get_scheduler()
    conn = get_db()
    schedules = q.get_all_schedules(conn)
    for sch in schedules:
        _register_job(sched, sch)

    _register_price_sync_job(sched)

    if backup_enabled():
        hour, minute = backup_cron_parts()
        sched.add_job(
            run_daily_backup,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=backup_timezone()),
            id="backup_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )

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

        ts = datetime.now(UTC).isoformat()
        base_notes = sch.get("notes") or ""
        tag = _catchup_tag(schedule_id)
        notes = f"{base_notes} {tag}" if base_notes else tag

        with _scoped_profile(conn, sch.get("profile_id")):
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
                portfolio_asset_id=sch.get("portfolio_asset_id"),
            )

            if tx_id:
                q.insert_schedule_occurrence(conn, schedule_id, now.isoformat(), tx_id)

            if tx_id and sch.get("portfolio_asset_id") and type_ in ("INVESTMENT_BUY", "INVESTMENT_SELL"):
                from models import TransactionCreate
                from services.transaction_svc import _resolve_investment_fields

                tx_row = q.get_transaction(conn, tx_id)
                if tx_row:
                    body = TransactionCreate(
                        timestamp=tx_row["timestamp"],
                        type=tx_row["type"],
                        entity_id=tx_row["entity_id"],
                        portfolio_asset_id=tx_row["portfolio_asset_id"],
                        quantity=tx_row["quantity"],
                        unit_price=tx_row["unit_price"],
                        total_value=tx_row["total_value"],
                        currency=tx_row["currency"],
                    )
                    qty, up, tv = _resolve_investment_fields(body)
                    if qty is not None or up is not None:
                        conn.execute(
                            "UPDATE transactions SET quantity = ?, unit_price = ?, total_value = ? WHERE id = ?",
                            (qty, up, tv, tx_id),
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
