"""Debt queries.

All rows are profile-scoped through the connection's active ``profile_id``.
The service owns the derived values; these helpers only read and write rows.
"""

import sqlite3
from typing import Any

DEBT_COLUMNS = (
    "direction",
    "counterparty_name",
    "description",
    "currency",
    "principal",
    "start_date",
    "term_months",
    "maturity_date",
    "installment_mode",
    "installment_amount",
    "principal_per_installment",
    "day_count",
    "rate_reset_mode",
    "review_period_months",
    "disbursement_mode",
    "disbursement_entity_id",
    "disbursement_date",
    "status",
    "settled_at",
    "settled_amount",
    "settlement_adjustment",
    "notes",
)

PAYMENT_COLUMNS = (
    "paid_at",
    "amount",
    "principal_amount",
    "interest_amount",
    "fees_amount",
    "insurance_amount",
    "other_amount",
    "kind",
    "transaction_id",
    "plan_entry_id",
    "notes",
)


def _pid(conn: sqlite3.Connection) -> int | None:
    return getattr(conn, "profile_id", None)


def _clause(conn: sqlite3.Connection, column: str = "profile_id") -> str:
    return f" AND {column} = ?" if _pid(conn) is not None else ""


def _params(conn: sqlite3.Connection) -> tuple:
    return (_pid(conn),) if _pid(conn) is not None else ()


def list_debts(
    conn: sqlite3.Connection,
    direction: str | None = None,
    status: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM debts WHERE 1=1" + _clause(conn)
    params: tuple = _params(conn)
    if direction is not None:
        query += " AND direction = ?"
        params += (direction,)
    if status is not None:
        query += " AND status = ?"
        params += (status,)
    query += " ORDER BY start_date DESC, id DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_debt(conn: sqlite3.Connection, debt_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM debts WHERE id = ?" + _clause(conn),
        (debt_id,) + _params(conn),
    ).fetchone()
    return dict(row) if row else None


def insert_debt(conn: sqlite3.Connection, **fields: Any) -> int:
    data = {key: fields.get(key) for key in DEBT_COLUMNS}
    columns = ", ".join(data)
    placeholders = ", ".join("?" for _ in data)
    cursor = conn.execute(
        f"INSERT INTO debts (profile_id, {columns}) VALUES (?, {placeholders})",
        (_pid(conn), *data.values()),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def update_debt(conn: sqlite3.Connection, debt_id: int, **fields: Any) -> int:
    data = {key: value for key, value in fields.items() if key in DEBT_COLUMNS}
    if not data:
        return 0
    assignments = ", ".join(f"{key} = ?" for key in data)
    cursor = conn.execute(
        f"UPDATE debts SET {assignments}, updated_at = datetime('now') WHERE id = ?" + _clause(conn),
        (*data.values(), debt_id) + _params(conn),
    )
    return cursor.rowcount


def delete_debt(conn: sqlite3.Connection, debt_id: int) -> int:
    cursor = conn.execute(
        "DELETE FROM debts WHERE id = ?" + _clause(conn),
        (debt_id,) + _params(conn),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------


def list_rates(conn: sqlite3.Connection, debt_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM debt_rates WHERE debt_id = ?" + _clause(conn) + " ORDER BY effective_from",
        (debt_id,) + _params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_rate_on(conn: sqlite3.Connection, debt_id: int, on_date: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM debt_rates WHERE debt_id = ? AND effective_from <= ?"
        + _clause(conn)
        + " ORDER BY effective_from DESC LIMIT 1",
        (debt_id, on_date) + _params(conn),
    ).fetchone()
    return dict(row) if row else None


def insert_rate(conn: sqlite3.Connection, debt_id: int, effective_from: str, annual_rate: float) -> int:
    cursor = conn.execute(
        "INSERT INTO debt_rates (profile_id, debt_id, effective_from, annual_rate) VALUES (?, ?, ?, ?)",
        (_pid(conn), debt_id, effective_from, annual_rate),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def delete_rate(conn: sqlite3.Connection, debt_id: int, effective_from: str) -> int:
    cursor = conn.execute(
        "DELETE FROM debt_rates WHERE debt_id = ? AND effective_from = ?" + _clause(conn),
        (debt_id, effective_from) + _params(conn),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


def list_payments(conn: sqlite3.Connection, debt_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM debt_payments WHERE debt_id = ?" + _clause(conn) + " ORDER BY paid_at, id",
        (debt_id,) + _params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_payment(conn: sqlite3.Connection, payment_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM debt_payments WHERE id = ?" + _clause(conn),
        (payment_id,) + _params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_payment_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM debt_payments WHERE transaction_id = ?" + _clause(conn),
        (transaction_id,) + _params(conn),
    ).fetchone()
    return dict(row) if row else None


def insert_payment(conn: sqlite3.Connection, debt_id: int, **fields: Any) -> int:
    data = {key: fields.get(key) for key in PAYMENT_COLUMNS}
    columns = ", ".join(data)
    placeholders = ", ".join("?" for _ in data)
    cursor = conn.execute(
        f"INSERT INTO debt_payments (profile_id, debt_id, {columns}) VALUES (?, ?, {placeholders})",
        (_pid(conn), debt_id, *data.values()),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def update_payment(conn: sqlite3.Connection, payment_id: int, **fields: Any) -> int:
    data = {key: value for key, value in fields.items() if key in PAYMENT_COLUMNS}
    if not data:
        return 0
    assignments = ", ".join(f"{key} = ?" for key in data)
    cursor = conn.execute(
        f"UPDATE debt_payments SET {assignments} WHERE id = ?" + _clause(conn),
        (*data.values(), payment_id) + _params(conn),
    )
    return cursor.rowcount


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> int:
    cursor = conn.execute(
        "DELETE FROM debt_payments WHERE id = ?" + _clause(conn),
        (payment_id,) + _params(conn),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Plan entries
# ---------------------------------------------------------------------------


def list_plan_entries(conn: sqlite3.Connection, debt_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM debt_plan_entries WHERE debt_id = ?" + _clause(conn) + " ORDER BY due_date",
        (debt_id,) + _params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_plan_entries_from(conn: sqlite3.Connection, debt_id: int, from_date: str) -> int:
    cursor = conn.execute(
        "DELETE FROM debt_plan_entries WHERE debt_id = ? AND due_date >= ?" + _clause(conn),
        (debt_id, from_date) + _params(conn),
    )
    return cursor.rowcount


def insert_plan_entry(
    conn: sqlite3.Connection,
    debt_id: int,
    period_no: int,
    due_date: str,
    payment_amount: float,
    principal_amount: float,
    interest_amount: float,
    fees_amount: float = 0.0,
    insurance_amount: float = 0.0,
    other_amount: float = 0.0,
) -> int:
    cursor = conn.execute(
        """INSERT INTO debt_plan_entries
           (profile_id, debt_id, period_no, due_date, payment_amount, principal_amount,
            interest_amount, fees_amount, insurance_amount, other_amount)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _pid(conn),
            debt_id,
            period_no,
            due_date,
            payment_amount,
            principal_amount,
            interest_amount,
            fees_amount,
            insurance_amount,
            other_amount,
        ),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Counterparties
# ---------------------------------------------------------------------------


def list_counterparties(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT counterparty_name, MAX(start_date) AS last_used FROM debts WHERE 1=1"
        + _clause(conn)
        + " GROUP BY counterparty_name COLLATE NOCASE ORDER BY last_used DESC, counterparty_name",
        _params(conn),
    ).fetchall()
    return [r["counterparty_name"] for r in rows]


def get_schedule_by_debt(conn: sqlite3.Connection, debt_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM schedules WHERE debt_id = ?" + _clause(conn) + " LIMIT 1",
        (debt_id,) + _params(conn),
    ).fetchone()
    return dict(row) if row else None
