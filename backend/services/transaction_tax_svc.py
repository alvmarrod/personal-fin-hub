from db.connection import get_db
from db import queries
from models import TransactionTaxCreate, TransactionTaxResponse


class TransactionTaxError(Exception):
    pass


class TransactionTaxNotFound(TransactionTaxError):
    pass


class TransactionNotFound(TransactionTaxError):
    pass


def create(body: TransactionTaxCreate) -> TransactionTaxResponse:
    conn = get_db()
    if not queries.get_transaction(conn, body.transaction_id):
        raise TransactionNotFound(f"Transaction {body.transaction_id} not found")
    tax_id = queries.create_tax(
        conn,
        transaction_id=body.transaction_id,
        tax_type=body.tax_type,
        tax_amount=body.tax_amount,
        currency=body.currency,
        tax_rate=body.tax_rate,
    )
    conn.commit()
    return TransactionTaxResponse(
        id=tax_id,
        transaction_id=body.transaction_id,
        tax_type=body.tax_type,
        tax_rate=body.tax_rate,
        tax_amount=body.tax_amount,
        currency=body.currency,
    )


def get(tax_id: int) -> TransactionTaxResponse:
    conn = get_db()
    row = queries.get_tax(conn, tax_id)
    if row is None:
        raise TransactionTaxNotFound(f"Tax {tax_id} not found")
    return TransactionTaxResponse(
        id=row["id"],
        transaction_id=row["transaction_id"],
        tax_type=row["tax_type"],
        tax_rate=row["tax_rate"],
        tax_amount=row["tax_amount"],
        currency=row["currency"],
    )


def list_all(transaction_id: int | None = None) -> list[TransactionTaxResponse]:
    conn = get_db()
    if transaction_id is not None:
        rows = queries.get_taxes_by_transaction(conn, transaction_id)
    else:
        rows = queries.get_all_taxes(conn)
    return [
        TransactionTaxResponse(
            id=r["id"],
            transaction_id=r["transaction_id"],
            tax_type=r["tax_type"],
            tax_rate=r["tax_rate"],
            tax_amount=r["tax_amount"],
            currency=r["currency"],
        )
        for r in rows
    ]


def update(tax_id: int, body: TransactionTaxCreate) -> TransactionTaxResponse:
    conn = get_db()
    existing = queries.get_tax(conn, tax_id)
    if existing is None:
        raise TransactionTaxNotFound(f"Tax {tax_id} not found")
    if not queries.get_transaction(conn, body.transaction_id):
        raise TransactionNotFound(f"Transaction {body.transaction_id} not found")
    queries.update_tax(
        conn,
        tax_id,
        transaction_id=body.transaction_id,
        tax_type=body.tax_type,
        tax_amount=body.tax_amount,
        currency=body.currency,
        tax_rate=body.tax_rate,
    )
    conn.commit()
    return TransactionTaxResponse(
        id=tax_id,
        transaction_id=body.transaction_id,
        tax_type=body.tax_type,
        tax_rate=body.tax_rate,
        tax_amount=body.tax_amount,
        currency=body.currency,
    )


def delete(tax_id: int) -> None:
    conn = get_db()
    existing = queries.get_tax(conn, tax_id)
    if existing is None:
        raise TransactionTaxNotFound(f"Tax {tax_id} not found")
    queries.delete_tax(conn, tax_id)
    conn.commit()
