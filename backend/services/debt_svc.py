"""Debt engine.

Everything about a debt is derived on request: outstanding principal, accrued
interest, the payment split, the next payment and the projection. The only
stored facts are the debt terms, its rate schedule, its payments and an
optional imported plan.

Dates are profile-timezone calendar dates stored as ``YYYY-MM-DD`` strings.
"""

import logging
import sqlite3
from calendar import monthrange
from datetime import date, datetime
from typing import Any

from db import debt_queries as q
from db import queries
from db.connection import get_db
from models import (
    DebtCancelBody,
    DebtCreate,
    DebtDetail,
    DebtDirection,
    DebtNextPayment,
    DebtPayment,
    DebtPaymentBody,
    DebtPaymentKind,
    DebtPlanEntry,
    DebtPlanImport,
    DebtRate,
    DebtRateBody,
    DebtResponse,
    DebtSettleBody,
    DebtStatus,
    DebtSummary,
    DebtUpdate,
    InstallmentMode,
    RateResetMode,
)
from services.currency_svc import PairNotFound, get_rate

logger = logging.getLogger(__name__)


class DebtError(Exception):
    """Base class for debt failures."""


class DebtNotFound(DebtError):
    pass


class DebtValidationError(DebtError):
    pass


# ---------------------------------------------------------------------------
# Dates and day counts
# ---------------------------------------------------------------------------


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _r(value: float) -> float:
    return round(value + 0.0, 2)


def _today(conn: sqlite3.Connection) -> date:
    return datetime.now(queries.profile_timezone(conn)).date()


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _days_30_360(start: date, end: date) -> int:
    d1 = min(start.day, 30)
    d2 = min(end.day, 30) if start.day >= 30 else end.day
    return (end.year - start.year) * 360 + (end.month - start.month) * 30 + (d2 - d1)


def _year_fraction(day_count: str, start: date, end: date) -> float:
    days = (end - start).days
    if day_count == "monthly":
        return days / monthrange(start.year, start.month)[1] / 12
    if day_count == "actual_360":
        return days / 360
    if day_count == "thirty_360":
        return _days_30_360(start, end) / 360
    return days / 365


# ---------------------------------------------------------------------------
# Rates and balances
# ---------------------------------------------------------------------------


def _rate_at(rates: list[dict], on_date: date) -> float:
    chosen = None
    for rate in rates:
        if _as_date(rate["effective_from"]) <= on_date:
            chosen = rate
        else:
            break
    if chosen is None and rates:
        chosen = rates[0]
    return float(chosen["annual_rate"]) if chosen else 0.0


def _outstanding(principal: float, payments: list[dict], as_of: date | None = None) -> float:
    paid = sum(float(p["principal_amount"]) for p in payments if as_of is None or _as_date(p["paid_at"]) <= as_of)
    return max(0.0, principal - paid)


def _last_paid(payments: list[dict], as_of: date | None = None) -> date | None:
    dates = [_as_date(p["paid_at"]) for p in payments if as_of is None or _as_date(p["paid_at"]) <= as_of]
    return max(dates) if dates else None


def _interest_between(
    debt: dict,
    rates: list[dict],
    outstanding: float,
    start: date,
    end: date,
) -> float:
    if end <= start or outstanding <= 0:
        return 0.0
    boundaries = {start, end}
    if debt["day_count"] == "monthly":
        cursor = _add_months(date(start.year, start.month, 1), 1)
        while cursor < end:
            boundaries.add(cursor)
            cursor = _add_months(cursor, 1)
    for rate in rates:
        effective = _as_date(rate["effective_from"])
        if start < effective < end:
            boundaries.add(effective)
    points = sorted(boundaries)
    total = 0.0
    for left, right in zip(points, points[1:], strict=False):
        if right <= left:
            continue
        annual = _rate_at(rates, left)
        total += outstanding * annual / 100 * _year_fraction(debt["day_count"], left, right)
    return total


def _accrued(debt: dict, rates: list[dict], payments: list[dict], as_of: date) -> float:
    last_paid = _last_paid(payments, as_of)
    start = last_paid if last_paid is not None else _as_date(debt["start_date"])
    if as_of <= start:
        return 0.0
    outstanding = _outstanding(float(debt["principal"]), payments, as_of)
    return _interest_between(debt, rates, outstanding, start, as_of)


def _current_rate(rates: list[dict], on_date: date) -> float:
    return _rate_at(rates, on_date)


def _next_due(debt: dict, payments: list[dict]) -> date:
    last_paid = _last_paid(payments)
    anchor = last_paid if last_paid is not None else _as_date(debt["start_date"])
    return _add_months(anchor, 1)


def _remaining_months(debt: dict, on_date: date) -> int:
    if debt["maturity_date"]:
        return max(0, _months_between(on_date, _as_date(debt["maturity_date"])))
    if debt["term_months"]:
        return max(0, int(debt["term_months"]) - _months_between(_as_date(debt["start_date"]), on_date))
    return 0


def _annuity(outstanding: float, annual_rate: float, months: int) -> float:
    if months <= 0:
        return outstanding
    monthly = annual_rate / 100 / 12
    if monthly == 0:
        return outstanding / months
    return outstanding * monthly / (1 - (1 + monthly) ** -months)


def _installment_amount(debt: dict, outstanding: float, annual_rate: float, on_date: date) -> float:
    stored = float(debt["installment_amount"]) if debt["installment_amount"] is not None else None
    if debt["rate_reset_mode"] == RateResetMode.KEEP_INSTALLMENT.value and stored:
        return stored
    months = _remaining_months(debt, on_date)
    if months <= 0:
        return stored or outstanding
    return _annuity(outstanding, annual_rate, months)


def _project(debt: dict, rates: list[dict], payments: list[dict], limit: int = 600) -> list[dict]:
    """Future rows at the current rate. A projection, not stored state."""
    if debt["status"] != DebtStatus.ACTIVE.value:
        return []
    outstanding = _outstanding(float(debt["principal"]), payments)
    if outstanding <= 0.005:
        return []
    last_paid = _last_paid(payments)
    anchor = last_paid if last_paid is not None else _as_date(debt["start_date"])
    due = _add_months(anchor, 1)
    annual = _current_rate(rates, anchor)
    future_rates = [{"effective_from": anchor.isoformat(), "annual_rate": annual}]
    mode = debt["installment_mode"]
    rows: list[dict] = []
    for _ in range(limit):
        if outstanding <= 0.005:
            break
        interest = _interest_between(debt, future_rates, outstanding, anchor, due)
        if mode == InstallmentMode.EQUAL_PRINCIPAL.value:
            principal = min(float(debt["principal_per_installment"] or 0.0), outstanding)
        elif mode == InstallmentMode.INTEREST_ONLY.value:
            principal = 0.0
        elif mode == InstallmentMode.MANUAL.value:
            amount = float(debt["installment_amount"] or 0.0)
            principal = min(max(0.0, amount - interest), outstanding)
        else:
            amount = _installment_amount(debt, outstanding, annual, anchor)
            principal = min(max(0.0, amount - interest), outstanding)
        payment = interest + principal
        rows.append(
            {
                "due_date": due.isoformat(),
                "payment": payment,
                "principal": principal,
                "interest": interest,
            }
        )
        outstanding -= principal
        anchor, due = due, _add_months(due, 1)
        if principal == 0 and mode != InstallmentMode.EQUAL_PAYMENT.value:
            break
    return rows


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


def _response(
    debt: dict,
    rates: list[dict],
    payments: list[dict],
    plan: list[dict] | None = None,
    detail: bool = False,
    as_of: date | None = None,
) -> DebtResponse:
    principal = float(debt["principal"])
    outstanding = _outstanding(principal, payments)
    today = as_of or date.today()
    accrued = _accrued(debt, rates, payments, today)
    projection = _project(debt, rates, payments)
    next_row = projection[0] if projection else None
    payload = {
        **debt,
        "current_rate": _current_rate(rates, today),
        "outstanding_principal": _r(outstanding),
        "accrued_interest": _r(accrued),
        "total_due": _r(outstanding + accrued),
        "progress_pct": _r((1 - outstanding / principal) * 100) if principal else 0.0,
        "next_payment_date": next_row["due_date"] if next_row else None,
        "next_payment_amount": _r(next_row["payment"]) if next_row else None,
    }
    if detail:
        return DebtDetail(
            **payload,
            rates=[DebtRate(**r) for r in rates],
            payments=[DebtPayment(**p) for p in payments],
            plan=[DebtPlanEntry(**e) for e in (plan or [])],
        )
    return DebtResponse(**payload)


def _load(conn: sqlite3.Connection, debt_id: int) -> tuple[dict, list[dict], list[dict]]:
    debt = q.get_debt(conn, debt_id)
    if debt is None:
        raise DebtNotFound(f"Debt {debt_id} not found")
    return debt, q.list_rates(conn, debt_id), q.list_payments(conn, debt_id)


def _clean(values: dict) -> dict:
    return {key: (value.isoformat() if isinstance(value, date) else value) for key, value in values.items()}


def _require_active(debt: dict) -> None:
    if debt["status"] != DebtStatus.ACTIVE.value:
        raise DebtValidationError("the debt is not active")


def _require_currency(conn: sqlite3.Connection, currency: str) -> None:
    row = conn.execute("SELECT 1 FROM currencies WHERE code = ? LIMIT 1", (currency,)).fetchone()
    if row is None:
        raise DebtValidationError(f"currency {currency} not found")


def _require_entity(conn: sqlite3.Connection, entity_id: int) -> None:
    if queries.get_entity(conn, entity_id) is None:
        raise DebtValidationError(f"entity {entity_id} not found")


def _transaction_type(debt: dict, draw: bool = False) -> str:
    payable = debt["direction"] == DebtDirection.PAYABLE.value
    if draw:
        return "DEBT_IN" if payable else "DEBT_OUT"
    return "DEBT_OUT" if payable else "DEBT_IN"


def _create_transaction(
    conn: sqlite3.Connection,
    debt: dict,
    when: date,
    amount: float,
    entity_id: int,
    draw: bool = False,
    notes: str | None = None,
) -> int:
    _require_entity(conn, entity_id)
    return queries.create_transaction(
        conn,
        timestamp=queries.profile_date_to_utc_instant(conn, when.isoformat()),
        type_=_transaction_type(debt, draw=draw),
        entity_id=entity_id,
        currency=debt["currency"],
        total_value=round(amount, 2),
        notes=notes,
    )


def _remove_job(schedule_id: int) -> None:
    try:
        from scheduler.scheduler import current_scheduler, remove_schedule

        if current_scheduler() is not None:
            remove_schedule(schedule_id)
    except Exception:
        logger.warning("Could not remove the scheduler job for schedule %s", schedule_id, exc_info=True)


def _register_job(schedule_id: int) -> None:
    try:
        from scheduler.scheduler import current_scheduler, sync_schedule

        if current_scheduler() is not None:
            sync_schedule(schedule_id)
    except Exception:
        logger.warning("Could not register the scheduler job for schedule %s", schedule_id, exc_info=True)


def _stop_schedule(conn: sqlite3.Connection, debt_id: int) -> None:
    schedule = q.get_schedule_by_debt(conn, debt_id)
    if schedule is None:
        return
    _remove_job(int(schedule["id"]))
    queries.delete_schedule_occurrences(conn, schedule["id"])
    queries.delete_schedule(conn, schedule["id"])


def _create_schedule(
    conn: sqlite3.Connection,
    debt: dict,
    entity_id: int,
    periodicity: str,
    first_date: date | None,
) -> None:
    _require_entity(conn, entity_id)
    start = first_date or _add_months(_as_date(debt["start_date"]), 1)
    rates = q.list_rates(conn, debt["id"])
    payments = q.list_payments(conn, debt["id"])
    outstanding = _outstanding(float(debt["principal"]), payments)
    annual = _current_rate(rates, start)
    if debt["installment_mode"] == InstallmentMode.EQUAL_PAYMENT.value:
        amount = _installment_amount(debt, outstanding, annual, start)
    elif debt["installment_mode"] == InstallmentMode.EQUAL_PRINCIPAL.value:
        amount = float(debt["principal_per_installment"] or 0.0) + _interest_between(
            debt, rates, outstanding, _last_paid(payments) or start, start
        )
    elif debt["installment_mode"] == InstallmentMode.INTEREST_ONLY.value:
        amount = _interest_between(debt, rates, outstanding, _last_paid(payments) or start, start)
    else:
        amount = float(debt["installment_amount"] or 0.0)
    schedule_id = queries.create_schedule(
        conn,
        description=f"Debt payment: {debt['counterparty_name']}",
        start_date=start.isoformat(),
        periodicity_type=periodicity,
        entity_id=entity_id,
        currency=debt["currency"],
        type_=_transaction_type(debt),
        total_value=round(amount, 2) if amount else None,
        notes=debt["notes"],
        debt_id=int(debt["id"]),
    )
    _register_job(schedule_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_debts(direction: str | None = None, status: str | None = None) -> list[DebtResponse]:
    conn = get_db()
    result = []
    today = _today(conn)
    for debt in q.list_debts(conn, direction=direction, status=status):
        result.append(
            _response(
                debt,
                q.list_rates(conn, debt["id"]),
                q.list_payments(conn, debt["id"]),
                as_of=today,
            )
        )
    return result


def get(debt_id: int) -> DebtDetail:
    conn = get_db()
    debt, rates, payments = _load(conn, debt_id)
    return _response(  # type: ignore[return-value]
        debt, rates, payments, q.list_plan_entries(conn, debt_id), detail=True, as_of=_today(conn)
    )


def create(body: DebtCreate) -> DebtDetail:
    conn = get_db()
    _require_currency(conn, body.currency)
    if body.disbursement_mode.value == "pocket" and body.disbursement_entity_id is not None:
        _require_entity(conn, body.disbursement_entity_id)
    values = _clean(body.model_dump(exclude={"annual_rate"}))
    debt_id = q.insert_debt(conn, **values, status=DebtStatus.ACTIVE.value)
    q.insert_rate(conn, debt_id, body.start_date.isoformat(), body.annual_rate)
    debt = q.get_debt(conn, debt_id)
    assert debt is not None
    if body.disbursement_mode.value == "pocket" and body.disbursement_entity_id is not None:
        _create_transaction(
            conn,
            debt,
            body.disbursement_date or body.start_date,
            body.principal,
            body.disbursement_entity_id,
            draw=True,
            notes=body.notes or "Debt disbursement",
        )
    if body.payment_periodicity is not None and body.payment_entity_id is not None:
        _create_schedule(conn, debt, body.payment_entity_id, body.payment_periodicity.value, body.first_payment_date)
    conn.commit()
    return get(debt_id)


def update(debt_id: int, body: DebtUpdate) -> DebtDetail:
    conn = get_db()
    debt, _, payments = _load(conn, debt_id)
    values = _clean(body.model_dump(exclude_none=True))
    if values.get("currency") and values["currency"] != debt["currency"]:
        _require_currency(conn, values["currency"])
        if payments:
            raise DebtValidationError("currency cannot change after a payment")
    if values.get("direction") and values["direction"] != debt["direction"] and payments:
        raise DebtValidationError("direction cannot change after a payment")
    if values.get("disbursement_entity_id"):
        _require_entity(conn, int(values["disbursement_entity_id"]))
    q.update_debt(conn, debt_id, **values)
    if body.payment_periodicity is not None and body.payment_entity_id is not None:
        _stop_schedule(conn, debt_id)
        updated = q.get_debt(conn, debt_id)
        assert updated is not None
        _create_schedule(conn, updated, body.payment_entity_id, body.payment_periodicity.value, body.first_payment_date)
    conn.commit()
    return get(debt_id)


def delete(debt_id: int) -> None:
    conn = get_db()
    debt, _, payments = _load(conn, debt_id)
    for payment in payments:
        if payment["transaction_id"] is not None:
            queries.delete_transaction(conn, int(payment["transaction_id"]))
    conn.execute("DELETE FROM debt_payments WHERE debt_id = ?", (debt_id,))
    q.delete_plan_entries_from(conn, debt_id, "0001-01-01")
    conn.execute("DELETE FROM debt_rates WHERE debt_id = ?", (debt_id,))
    _stop_schedule(conn, debt_id)
    q.delete_debt(conn, debt_id)
    conn.commit()


def add_rate(debt_id: int, body: DebtRateBody) -> DebtDetail:
    conn = get_db()
    debt, rates, payments = _load(conn, debt_id)
    _require_active(debt)
    try:
        q.insert_rate(conn, debt_id, body.effective_from.isoformat(), body.annual_rate)
    except sqlite3.IntegrityError as exc:
        raise DebtValidationError("a rate already exists for that date") from exc
    if debt["installment_mode"] == InstallmentMode.EQUAL_PAYMENT.value:
        outstanding = _outstanding(float(debt["principal"]), payments)
        amount = _installment_amount(debt, outstanding, body.annual_rate, body.effective_from)
        q.update_debt(conn, debt_id, installment_amount=round(amount, 2))
    conn.commit()
    return get(debt_id)


def _split(
    debt: dict,
    rates: list[dict],
    payments: list[dict],
    body: DebtPaymentBody,
    paid_at: date,
    kind: DebtPaymentKind,
) -> tuple[float, float, float, float, float, float]:
    outstanding = _outstanding(float(debt["principal"]), payments)
    other = round(body.fees_amount + body.insurance_amount + body.other_amount, 2)
    if body.principal_amount is not None and body.interest_amount is not None:
        return (
            round(body.amount, 2),
            round(body.principal_amount, 2),
            round(body.interest_amount, 2),
            round(body.fees_amount, 2),
            round(body.insurance_amount, 2),
            round(body.other_amount, 2),
        )
    accrued = _accrued(debt, rates, payments, paid_at)
    if body.principal_only:
        interest = 0.0
    else:
        interest = min(accrued, max(0.0, body.amount - other))
        if kind != DebtPaymentKind.SETTLEMENT and interest + 0.005 < accrued:
            raise DebtValidationError("the payment does not cover accrued interest")
    principal = round(body.amount - other - interest, 2)
    if principal < -0.005:
        raise DebtValidationError("the payment does not cover interest and fees")
    if principal > outstanding + 0.005:
        raise DebtValidationError("the payment exceeds the outstanding principal; use settle")
    principal = min(principal, outstanding)
    return (
        round(body.amount, 2),
        round(principal, 2),
        round(interest, 2),
        round(body.fees_amount, 2),
        round(body.insurance_amount, 2),
        round(body.other_amount, 2),
    )


def record_payment(debt_id: int, body: DebtPaymentBody) -> DebtDetail:
    conn = get_db()
    debt, rates, payments = _load(conn, debt_id)
    _require_active(debt)
    if body.kind == DebtPaymentKind.SETTLEMENT:
        raise DebtValidationError("use settle for a settlement payment")
    paid_at = body.paid_at
    amount, principal, interest, fees, insurance, other = _split(debt, rates, payments, body, paid_at, body.kind)
    transaction_id = _create_transaction(
        conn,
        debt,
        paid_at,
        amount,
        body.entity_id,
        notes=body.notes or f"Debt payment: {debt['counterparty_name']}",
    )
    q.insert_payment(
        conn,
        debt_id,
        paid_at=paid_at.isoformat(),
        amount=amount,
        principal_amount=principal,
        interest_amount=interest,
        fees_amount=fees,
        insurance_amount=insurance,
        other_amount=other,
        kind=body.kind.value,
        transaction_id=transaction_id,
        plan_entry_id=None,
        notes=body.notes,
    )
    if _outstanding(float(debt["principal"]), payments) - principal <= 0.005:
        q.update_debt(
            conn,
            debt_id,
            status=DebtStatus.SETTLED.value,
            settled_at=paid_at.isoformat(),
            settled_amount=amount,
            settlement_adjustment=0.0,
        )
        _stop_schedule(conn, debt_id)
    conn.commit()
    return get(debt_id)


def delete_payment(debt_id: int, payment_id: int) -> DebtDetail:
    conn = get_db()
    debt, _, _ = _load(conn, debt_id)
    payment = q.get_payment(conn, payment_id)
    if payment is None or payment["debt_id"] != debt_id:
        raise DebtNotFound(f"Payment {payment_id} not found")
    if payment["transaction_id"] is not None:
        queries.delete_transaction(conn, int(payment["transaction_id"]))
    q.delete_payment(conn, payment_id)
    if debt["status"] == DebtStatus.SETTLED.value:
        q.update_debt(
            conn,
            debt_id,
            status=DebtStatus.ACTIVE.value,
            settled_at=None,
            settled_amount=None,
            settlement_adjustment=None,
        )
    conn.commit()
    return get(debt_id)


def settle(debt_id: int, body: DebtSettleBody) -> DebtDetail:
    conn = get_db()
    debt, rates, payments = _load(conn, debt_id)
    _require_active(debt)
    outstanding = _outstanding(float(debt["principal"]), payments)
    accrued = _accrued(debt, rates, payments, body.settled_at)
    payoff = round(outstanding + accrued, 2)
    amount = round(body.amount, 2) if body.amount is not None else payoff
    adjustment = round(amount - payoff, 2)
    transaction_id = _create_transaction(
        conn,
        debt,
        body.settled_at,
        amount,
        body.entity_id,
        notes=body.notes or f"Debt settlement: {debt['counterparty_name']}",
    )
    q.insert_payment(
        conn,
        debt_id,
        paid_at=body.settled_at.isoformat(),
        amount=amount,
        principal_amount=round(outstanding, 2),
        interest_amount=round(accrued, 2),
        fees_amount=0.0,
        insurance_amount=0.0,
        other_amount=adjustment,
        kind=DebtPaymentKind.SETTLEMENT.value,
        transaction_id=transaction_id,
        plan_entry_id=None,
        notes=body.notes,
    )
    q.update_debt(
        conn,
        debt_id,
        status=DebtStatus.SETTLED.value,
        settled_at=body.settled_at.isoformat(),
        settled_amount=amount,
        settlement_adjustment=adjustment,
    )
    _stop_schedule(conn, debt_id)
    conn.commit()
    return get(debt_id)


def cancel(debt_id: int, body: DebtCancelBody) -> DebtDetail:
    conn = get_db()
    debt, _, _ = _load(conn, debt_id)
    _require_active(debt)
    q.update_debt(
        conn,
        debt_id,
        status=DebtStatus.CANCELLED.value,
        settled_at=body.cancelled_at.isoformat(),
        settled_amount=0.0,
        settlement_adjustment=None,
        notes=body.notes or debt["notes"],
    )
    _stop_schedule(conn, debt_id)
    conn.commit()
    return get(debt_id)


def get_plan(debt_id: int) -> list[dict]:
    conn = get_db()
    _load(conn, debt_id)
    return q.list_plan_entries(conn, debt_id)


def import_plan(debt_id: int, body: DebtPlanImport) -> list[dict]:
    conn = get_db()
    _load(conn, debt_id)
    replace_from = body.replace_from or body.entries[0].due_date
    q.delete_plan_entries_from(conn, debt_id, replace_from.isoformat())
    for period, entry in enumerate(body.entries, start=1):
        q.insert_plan_entry(
            conn,
            debt_id,
            period,
            entry.due_date.isoformat(),
            entry.payment_amount,
            entry.principal_amount,
            entry.interest_amount,
            entry.fees_amount,
            entry.insurance_amount,
            entry.other_amount,
        )
    conn.commit()
    return q.list_plan_entries(conn, debt_id)


def scheduled_payment(
    conn: sqlite3.Connection,
    schedule: dict,
    occurrence_date: date,
    timestamp: str,
) -> int | None:
    """Materialize one debt occurrence from its schedule. Called by the scheduler."""
    debt_id = int(schedule["debt_id"])
    debt = q.get_debt(conn, debt_id)
    if debt is None or debt["status"] != DebtStatus.ACTIVE.value:
        _stop_schedule(conn, debt_id)
        return None
    rates = q.list_rates(conn, debt_id)
    payments = q.list_payments(conn, debt_id)
    outstanding = _outstanding(float(debt["principal"]), payments)
    plan = q.list_plan_entries(conn, debt_id)
    entry = next((e for e in plan if e["due_date"] == occurrence_date.isoformat()), None)
    plan_entry_id: int | None = None
    if entry is not None:
        amount = float(entry["payment_amount"])
        principal = float(entry["principal_amount"])
        interest = float(entry["interest_amount"])
        fees = float(entry["fees_amount"])
        insurance = float(entry["insurance_amount"])
        other = float(entry["other_amount"])
        plan_entry_id = int(entry["id"])
    else:
        fees = insurance = other = 0.0
        mode = debt["installment_mode"]
        if mode == InstallmentMode.EQUAL_PRINCIPAL.value:
            principal = min(float(debt["principal_per_installment"] or 0.0), outstanding)
            interest = _accrued(debt, rates, payments, occurrence_date)
            amount = principal + interest
        elif mode == InstallmentMode.INTEREST_ONLY.value:
            principal = 0.0
            interest = _accrued(debt, rates, payments, occurrence_date)
            amount = interest
        else:
            amount = float(schedule["total_value"] or 0.0)
            if amount <= 0:
                annual = _current_rate(rates, occurrence_date)
                amount = _installment_amount(debt, outstanding, annual, occurrence_date)
            interest = min(_accrued(debt, rates, payments, occurrence_date), amount)
            principal = min(amount - interest, outstanding)
            amount = principal + interest
    if amount <= 0:
        return None
    tx_id = queries.create_transaction(
        conn,
        timestamp=timestamp,
        type_=_transaction_type(debt),
        entity_id=int(schedule["entity_id"]),
        currency=debt["currency"],
        total_value=round(amount, 2),
        notes=schedule.get("notes") or f"Debt payment: {debt['counterparty_name']}",
    )
    q.insert_payment(
        conn,
        debt_id,
        paid_at=occurrence_date.isoformat(),
        amount=round(amount, 2),
        principal_amount=round(principal, 2),
        interest_amount=round(interest, 2),
        fees_amount=round(fees, 2),
        insurance_amount=round(insurance, 2),
        other_amount=round(other, 2),
        kind=DebtPaymentKind.REGULAR.value,
        transaction_id=tx_id,
        plan_entry_id=plan_entry_id,
        notes=None,
    )
    if outstanding - principal <= 0.005:
        q.update_debt(
            conn,
            debt_id,
            status=DebtStatus.SETTLED.value,
            settled_at=occurrence_date.isoformat(),
            settled_amount=round(amount, 2),
            settlement_adjustment=0.0,
        )
        _stop_schedule(conn, debt_id)
    return tx_id


def _sync_status(conn: sqlite3.Connection, debt_id: int) -> None:
    debt = q.get_debt(conn, debt_id)
    if debt is None:
        return
    payments = q.list_payments(conn, debt_id)
    outstanding = _outstanding(float(debt["principal"]), payments)
    settled = debt["status"] == DebtStatus.SETTLED.value
    if settled and outstanding > 0.005:
        q.update_debt(
            conn,
            debt_id,
            status=DebtStatus.ACTIVE.value,
            settled_at=None,
            settled_amount=None,
            settlement_adjustment=None,
        )
    elif not settled and debt["status"] == DebtStatus.ACTIVE.value and payments and outstanding <= 0.005:
        last = payments[-1]
        q.update_debt(
            conn,
            debt_id,
            status=DebtStatus.SETTLED.value,
            settled_at=last["paid_at"],
            settled_amount=round(sum(float(p["amount"]) for p in payments), 2),
            settlement_adjustment=0.0,
        )


def reconcile_transaction(conn: sqlite3.Connection, transaction_id: int) -> None:
    """Re-derive a linked payment after its transaction is edited."""
    payment = q.get_payment_by_transaction(conn, transaction_id)
    if payment is None:
        return
    tx = queries.get_transaction(conn, transaction_id)
    debt = q.get_debt(conn, int(payment["debt_id"]))
    if tx is None or debt is None:
        q.delete_payment(conn, payment["id"])
        return
    if tx["type"] not in ("DEBT_IN", "DEBT_OUT") or tx["currency"] != debt["currency"]:
        q.delete_payment(conn, payment["id"])
        _sync_status(conn, int(payment["debt_id"]))
        return
    amount = round(float(tx["total_value"] or 0.0), 2)
    paid_at = queries.utc_instant_to_profile_date(conn, tx["timestamp"])
    if amount <= 0:
        q.delete_payment(conn, payment["id"])
        _sync_status(conn, int(payment["debt_id"]))
        return
    if abs(float(payment["amount"]) - amount) < 0.005 and payment["paid_at"] == paid_at:
        return
    other = round(
        float(payment["fees_amount"]) + float(payment["insurance_amount"]) + float(payment["other_amount"]),
        2,
    )
    rates = q.list_rates(conn, int(payment["debt_id"]))
    payments_before = [p for p in q.list_payments(conn, int(payment["debt_id"])) if p["id"] != payment["id"]]
    outstanding = _outstanding(float(debt["principal"]), payments_before)
    accrued = _accrued(debt, rates, payments_before, _as_date(paid_at))
    interest = min(accrued, max(0.0, amount - other))
    principal = min(max(0.0, amount - other - interest), outstanding)
    q.update_payment(
        conn,
        payment["id"],
        paid_at=paid_at,
        amount=amount,
        principal_amount=round(principal, 2),
        interest_amount=round(interest, 2),
    )
    _sync_status(conn, int(payment["debt_id"]))


def unlink_transaction(conn: sqlite3.Connection, transaction_id: int) -> None:
    """Drop the debt payment when its transaction is deleted."""
    payment = q.get_payment_by_transaction(conn, transaction_id)
    if payment is None:
        return
    debt_id = int(payment["debt_id"])
    q.delete_payment(conn, payment["id"])
    _sync_status(conn, debt_id)


def _convert(conn: sqlite3.Connection, value: float, currency: str, display: str) -> float:
    if currency == display:
        return value
    try:
        return value * get_rate(currency, display).rate
    except PairNotFound:
        return value


def summary(display_currency: str) -> DebtSummary:
    conn = get_db()
    payable = receivable = 0.0
    payable_accrued = receivable_accrued = 0.0
    payable_count = receivable_count = 0
    next_payable: DebtNextPayment | None = None
    next_receivable: DebtNextPayment | None = None
    today = _today(conn)
    for debt in q.list_debts(conn, status=DebtStatus.ACTIVE.value):
        rates = q.list_rates(conn, debt["id"])
        payments = q.list_payments(conn, debt["id"])
        outstanding = _convert(
            conn, _outstanding(float(debt["principal"]), payments), debt["currency"], display_currency
        )
        accrued = _convert(
            conn,
            _accrued(debt, rates, payments, today),
            debt["currency"],
            display_currency,
        )
        projection = _project(debt, rates, payments)
        nxt = (
            DebtNextPayment(
                debt_id=debt["id"],
                counterparty_name=debt["counterparty_name"],
                due_date=_as_date(projection[0]["due_date"]),
                amount=_convert(conn, projection[0]["payment"], debt["currency"], display_currency),
            )
            if projection
            else None
        )
        if debt["direction"] == DebtDirection.PAYABLE.value:
            payable += outstanding
            payable_accrued += accrued
            payable_count += 1
            if nxt is not None and (next_payable is None or nxt.due_date < next_payable.due_date):
                next_payable = nxt
        else:
            receivable += outstanding
            receivable_accrued += accrued
            receivable_count += 1
            if nxt is not None and (next_receivable is None or nxt.due_date < next_receivable.due_date):
                next_receivable = nxt
    return DebtSummary(
        display_currency=display_currency,
        payable=_r(payable),
        receivable=_r(receivable),
        payable_count=payable_count,
        receivable_count=receivable_count,
        payable_accrued_interest=_r(payable_accrued),
        receivable_accrued_interest=_r(receivable_accrued),
        next_payable=next_payable,
        next_receivable=next_receivable,
    )


def counterparties() -> list[str]:
    return q.list_counterparties(get_db())
