from db.connection import get_db
from db import queries
from models import FiscalExemptionCreate, FiscalExemptionResponse


class FiscalExemptionError(Exception):
    pass


class FiscalExemptionNotFound(FiscalExemptionError):
    pass


class FiscalExemptionHasDependents(FiscalExemptionError):
    pass


def create(body: FiscalExemptionCreate) -> FiscalExemptionResponse:
    conn = get_db()
    exemption_id = queries.create_fiscal_exemption(
        conn,
        exemption_type=body.exemption_type,
        description=body.description,
        exemption_amount=body.exemption_amount,
        exemption_rate=body.exemption_rate,
        exemption_rate_limit=body.exemption_rate_limit,
    )
    conn.commit()
    return FiscalExemptionResponse(
        id=exemption_id,
        exemption_type=body.exemption_type,
        description=body.description,
        exemption_amount=body.exemption_amount,
        exemption_rate=body.exemption_rate,
        exemption_rate_limit=body.exemption_rate_limit,
    )


def get(exemption_id: int) -> FiscalExemptionResponse:
    conn = get_db()
    row = queries.get_fiscal_exemption(conn, exemption_id)
    if row is None:
        raise FiscalExemptionNotFound(f"Fiscal exemption {exemption_id} not found")
    return FiscalExemptionResponse(
        id=row["id"],
        exemption_type=row["exemption_type"],
        description=row["description"],
        exemption_amount=row["exemption_amount"],
        exemption_rate=row["exemption_rate"],
        exemption_rate_limit=row["exemption_rate_limit"],
    )


def list_all() -> list[FiscalExemptionResponse]:
    conn = get_db()
    rows = queries.get_all_fiscal_exemptions(conn)
    return [
        FiscalExemptionResponse(
            id=r["id"],
            exemption_type=r["exemption_type"],
            description=r["description"],
            exemption_amount=r["exemption_amount"],
            exemption_rate=r["exemption_rate"],
            exemption_rate_limit=r["exemption_rate_limit"],
        )
        for r in rows
    ]


def update(exemption_id: int, body: FiscalExemptionCreate) -> FiscalExemptionResponse:
    conn = get_db()
    existing = queries.get_fiscal_exemption(conn, exemption_id)
    if existing is None:
        raise FiscalExemptionNotFound(f"Fiscal exemption {exemption_id} not found")
    queries.update_fiscal_exemption(
        conn,
        exemption_id,
        exemption_type=body.exemption_type,
        description=body.description,
        exemption_amount=body.exemption_amount,
        exemption_rate=body.exemption_rate,
        exemption_rate_limit=body.exemption_rate_limit,
    )
    conn.commit()
    return FiscalExemptionResponse(
        id=exemption_id,
        exemption_type=body.exemption_type,
        description=body.description,
        exemption_amount=body.exemption_amount,
        exemption_rate=body.exemption_rate,
        exemption_rate_limit=body.exemption_rate_limit,
    )


def delete(exemption_id: int) -> None:
    conn = get_db()
    existing = queries.get_fiscal_exemption(conn, exemption_id)
    if existing is None:
        raise FiscalExemptionNotFound(f"Fiscal exemption {exemption_id} not found")
    if queries.fiscal_exemption_has_dependents(conn, exemption_id):
        raise FiscalExemptionHasDependents(
            f"Fiscal exemption {exemption_id} has transactions referencing it"
        )
    queries.delete_fiscal_exemption(conn, exemption_id)
    conn.commit()
