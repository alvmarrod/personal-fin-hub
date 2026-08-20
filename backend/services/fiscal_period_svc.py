from datetime import date

from db import queries
from db.connection import get_db
from models import FiscalPeriodCreate, FiscalPeriodResponse


class FiscalPeriodError(Exception):
    pass


class FiscalPeriodNotFound(FiscalPeriodError):
    pass


class FiscalPeriodOverlap(FiscalPeriodError):
    pass


def _to_date(value: date | str | None) -> date:
    if value is None:
        return date.max
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _overlaps_existing(conn, start_date: date, end_date: date | None, exclude_id: int | None = None) -> bool:
    start = _to_date(start_date)
    end = _to_date(end_date)
    for period in queries.get_all_fiscal_periods(conn):
        if exclude_id is not None and period["id"] == exclude_id:
            continue
        p_start = _to_date(period["start_date"])
        p_end = _to_date(period["end_date"])
        if start <= p_end and p_start <= end:
            return True
    return False


def _response(row: dict) -> FiscalPeriodResponse:
    return FiscalPeriodResponse(
        id=row["id"],
        rule_key=row["rule_key"],
        start_date=_to_date(row["start_date"]),
        end_date=row["end_date"] and date.fromisoformat(row["end_date"]),
    )


def create(body: FiscalPeriodCreate) -> FiscalPeriodResponse:
    conn = get_db()
    if _overlaps_existing(conn, body.start_date, body.end_date):
        raise FiscalPeriodOverlap("Fiscal period overlaps an existing period")
    period_id = queries.create_fiscal_period(
        conn,
        rule_key=body.rule_key,
        start_date=body.start_date.isoformat(),
        end_date=body.end_date.isoformat() if body.end_date else None,
    )
    conn.commit()
    return FiscalPeriodResponse(
        id=period_id, rule_key=body.rule_key, start_date=body.start_date, end_date=body.end_date
    )


def get(period_id: int) -> FiscalPeriodResponse:
    conn = get_db()
    row = queries.get_fiscal_period(conn, period_id)
    if row is None:
        raise FiscalPeriodNotFound(f"Fiscal period {period_id} not found")
    return _response(row)


def list_all() -> list[FiscalPeriodResponse]:
    conn = get_db()
    return [_response(row) for row in queries.get_all_fiscal_periods(conn)]


def update(period_id: int, body: FiscalPeriodCreate) -> FiscalPeriodResponse:
    conn = get_db()
    if queries.get_fiscal_period(conn, period_id) is None:
        raise FiscalPeriodNotFound(f"Fiscal period {period_id} not found")
    if _overlaps_existing(conn, body.start_date, body.end_date, exclude_id=period_id):
        raise FiscalPeriodOverlap("Fiscal period overlaps an existing period")
    queries.update_fiscal_period(
        conn,
        period_id,
        rule_key=body.rule_key,
        start_date=body.start_date.isoformat(),
        end_date=body.end_date.isoformat() if body.end_date else None,
    )
    conn.commit()
    return FiscalPeriodResponse(
        id=period_id, rule_key=body.rule_key, start_date=body.start_date, end_date=body.end_date
    )


def delete(period_id: int) -> None:
    conn = get_db()
    if queries.get_fiscal_period(conn, period_id) is None:
        raise FiscalPeriodNotFound(f"Fiscal period {period_id} not found")
    queries.delete_fiscal_period(conn, period_id)
    conn.commit()
