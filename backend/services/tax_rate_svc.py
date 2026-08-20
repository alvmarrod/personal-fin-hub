"""Tax rate CRUD service (§17.8, §10.2)."""

from db import queries
from db.connection import get_db
from models import TaxRateCreate, TaxRateResponse


class TaxRateError(Exception):
    pass


class TaxRateNotFound(TaxRateError):
    pass


def _to_response(row: dict) -> TaxRateResponse:
    return TaxRateResponse(
        id=row["id"],
        ruleset_key=row["ruleset_key"],
        category=row["category"],
        from_amount=row["from_amount"],
        to_amount=row["to_amount"],
        rate=row["rate"],
        year_start=row.get("year_start"),
    )


def create(body: TaxRateCreate) -> TaxRateResponse:
    conn = get_db()
    rate_id = queries.create_tax_rate(
        conn,
        ruleset_key=body.ruleset_key,
        category=body.category,
        from_amount=body.from_amount,
        rate=body.rate,
        to_amount=body.to_amount,
        year_start=body.year_start,
    )
    conn.commit()
    row = queries.get_tax_rate(conn, rate_id)
    if row is None:
        raise TaxRateNotFound(f"Tax rate {rate_id} not found after create")
    return _to_response(row)


def get(rate_id: int) -> TaxRateResponse:
    conn = get_db()
    row = queries.get_tax_rate(conn, rate_id)
    if row is None:
        raise TaxRateNotFound(f"Tax rate {rate_id} not found")
    return _to_response(row)


def list_all(
    ruleset_key: str | None = None,
    category: str | None = None,
    year_start: int | None = None,
) -> list[TaxRateResponse]:
    conn = get_db()
    if ruleset_key:
        rows = queries.get_tax_rates_for_ruleset(conn, ruleset_key, category, year_start)
    else:
        rows = queries.get_all_tax_rates(conn)
    return [_to_response(r) for r in rows]


def update(rate_id: int, body: TaxRateCreate) -> TaxRateResponse:
    conn = get_db()
    if queries.get_tax_rate(conn, rate_id) is None:
        raise TaxRateNotFound(f"Tax rate {rate_id} not found")
    queries.update_tax_rate(
        conn,
        rate_id,
        ruleset_key=body.ruleset_key,
        category=body.category,
        from_amount=body.from_amount,
        rate=body.rate,
        to_amount=body.to_amount,
        year_start=body.year_start,
    )
    conn.commit()
    row = queries.get_tax_rate(conn, rate_id)
    if row is None:
        raise TaxRateNotFound(f"Tax rate {rate_id} not found after update")
    return _to_response(row)


def delete(rate_id: int) -> None:
    conn = get_db()
    if queries.get_tax_rate(conn, rate_id) is None:
        raise TaxRateNotFound(f"Tax rate {rate_id} not found")
    queries.delete_tax_rate(conn, rate_id)
    conn.commit()
