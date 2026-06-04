import sqlite3

from db.connection import get_db
from db import queries
from models import (
    TransactionCreate,
    TransactionFeeCreate,
    TransferCreate,
    TransferResponse,
)
from models.enums import FeeNature, FeeType, TransactionType
from services.transaction_svc import FKNotFound, create as create_transaction
from services.transaction_fee_svc import create as create_fee


class TransferError(Exception):
    pass


def create(body: TransferCreate) -> TransferResponse:
    conn = get_db()
    try:
        if not queries.get_entity(conn, body.from_entity_id):
            raise FKNotFound(f"Entity {body.from_entity_id} not found")
        if not queries.get_entity(conn, body.to_entity_id):
            raise FKNotFound(f"Entity {body.to_entity_id} not found")
        if not queries.code_exists(conn, body.currency):
            raise FKNotFound(f"Currency '{body.currency}' not found")

        out_tx = create_transaction(
            TransactionCreate(
                timestamp=body.timestamp,
                type=TransactionType.MONEY_OUT,
                entity_id=body.from_entity_id,
                currency=body.currency,
                total_value=body.amount,
                notes=body.notes,
            ),
            conn=conn,
        )
        in_tx = create_transaction(
            TransactionCreate(
                timestamp=body.timestamp,
                type=TransactionType.MONEY_IN,
                entity_id=body.to_entity_id,
                currency=body.currency,
                total_value=body.amount,
                notes=body.notes,
            ),
            conn=conn,
        )
        fees = [
            create_fee(
                TransactionFeeCreate(
                    transaction_id=out_tx.id,
                    fee_type=f.fee_type,
                    nature=f.nature,
                    fixed_amount=f.fixed_amount,
                    percentage=f.percentage,
                    currency=f.currency,
                ),
                conn=conn,
            )
            for f in body.fees
        ]
        conn.commit()
        return TransferResponse(
            from_transaction=out_tx,
            to_transaction=in_tx,
            fees=fees,
        )
    except FKNotFound:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
