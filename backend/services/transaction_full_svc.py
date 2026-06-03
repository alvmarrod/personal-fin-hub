import sqlite3

from db.connection import get_db
from models import (
    FullTransactionCreate,
    FullTransactionResponse,
    TransactionFeeCreate,
    TransactionTaxCreate,
)
from services.transaction_svc import FKNotFound, TransactionError, create as create_transaction
from services.transaction_fee_svc import create as create_fee
from services.transaction_tax_svc import create as create_tax


class FullTransactionError(Exception):
    pass


def create(body: FullTransactionCreate) -> FullTransactionResponse:
    conn = get_db()
    try:
        tx = create_transaction(body.transaction, conn=conn)
        fees = [
            create_fee(
                TransactionFeeCreate(
                    transaction_id=tx.id,
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
        taxes = [
            create_tax(
                TransactionTaxCreate(
                    transaction_id=tx.id,
                    tax_type=t.tax_type,
                    tax_rate=t.tax_rate,
                    tax_amount=t.tax_amount,
                    currency=t.currency,
                ),
                conn=conn,
            )
            for t in body.taxes
        ]
        conn.commit()
        return FullTransactionResponse(transaction=tx, fees=fees, taxes=taxes)
    except FKNotFound:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
