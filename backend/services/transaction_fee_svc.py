import sqlite3

from db.connection import get_db
from db import queries
from models import TransactionFeeCreate, TransactionFeeResponse
from models.enums import FeeNature, FeeType


class TransactionFeeError(Exception):
    pass


class TransactionFeeNotFound(TransactionFeeError):
    pass


class TransactionNotFound(TransactionFeeError):
    pass


def create(body: TransactionFeeCreate, conn: sqlite3.Connection | None = None) -> TransactionFeeResponse:
    if conn is None:
        conn = get_db()
        should_commit = True
    else:
        should_commit = False
    if not queries.get_transaction(conn, body.transaction_id):
        raise TransactionNotFound(f"Transaction {body.transaction_id} not found")
    fee_id = queries.create_fee(
        conn,
        transaction_id=body.transaction_id,
        fee_type=body.fee_type.value,
        nature=body.nature.value,
        currency=body.currency,
        fixed_amount=body.fixed_amount,
        percentage=body.percentage,
    )
    if should_commit:
        conn.commit()
    return TransactionFeeResponse(
        id=fee_id,
        transaction_id=body.transaction_id,
        fee_type=body.fee_type,
        nature=body.nature,
        fixed_amount=body.fixed_amount,
        percentage=body.percentage,
        currency=body.currency,
    )


def get(fee_id: int) -> TransactionFeeResponse:
    conn = get_db()
    row = queries.get_fee(conn, fee_id)
    if row is None:
        raise TransactionFeeNotFound(f"Fee {fee_id} not found")
    return TransactionFeeResponse(
        id=row["id"],
        transaction_id=row["transaction_id"],
        fee_type=FeeType(row["fee_type"]),
        nature=FeeNature(row["nature"]),
        fixed_amount=row["fixed_amount"],
        percentage=row["percentage"],
        currency=row["currency"],
    )


def list_all(transaction_id: int | None = None) -> list[TransactionFeeResponse]:
    conn = get_db()
    if transaction_id is not None:
        rows = queries.get_fees_by_transaction(conn, transaction_id)
    else:
        rows = queries.get_all_fees(conn)
    return [
        TransactionFeeResponse(
            id=r["id"],
            transaction_id=r["transaction_id"],
            fee_type=FeeType(r["fee_type"]),
            nature=FeeNature(r["nature"]),
            fixed_amount=r["fixed_amount"],
            percentage=r["percentage"],
            currency=r["currency"],
        )
        for r in rows
    ]


def update(fee_id: int, body: TransactionFeeCreate) -> TransactionFeeResponse:
    conn = get_db()
    existing = queries.get_fee(conn, fee_id)
    if existing is None:
        raise TransactionFeeNotFound(f"Fee {fee_id} not found")
    if not queries.get_transaction(conn, body.transaction_id):
        raise TransactionNotFound(f"Transaction {body.transaction_id} not found")
    queries.update_fee(
        conn,
        fee_id,
        transaction_id=body.transaction_id,
        fee_type=body.fee_type.value,
        nature=body.nature.value,
        currency=body.currency,
        fixed_amount=body.fixed_amount,
        percentage=body.percentage,
    )
    conn.commit()
    return TransactionFeeResponse(
        id=fee_id,
        transaction_id=body.transaction_id,
        fee_type=body.fee_type,
        nature=body.nature,
        fixed_amount=body.fixed_amount,
        percentage=body.percentage,
        currency=body.currency,
    )


def delete(fee_id: int) -> None:
    conn = get_db()
    existing = queries.get_fee(conn, fee_id)
    if existing is None:
        raise TransactionFeeNotFound(f"Fee {fee_id} not found")
    queries.delete_fee(conn, fee_id)
    conn.commit()
