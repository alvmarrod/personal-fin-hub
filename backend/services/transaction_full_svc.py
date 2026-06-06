import sqlite3

from db.connection import get_db
from db import queries
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


class SnapshotConstraintError(FullTransactionError):
    pass


def _check_snapshot_constraint(conn, body: FullTransactionCreate) -> None:
    snapshot = queries.get_latest_snapshot(conn, body.transaction.entity_id, body.transaction.currency)
    if snapshot is None:
        return
    ts = body.transaction.timestamp
    if hasattr(ts, 'isoformat'):
        ts_iso = ts.isoformat()
    else:
        ts_iso = str(ts)
    if ts_iso <= snapshot["timestamp"]:
        raise SnapshotConstraintError(
            f"Transaction timestamp {ts_iso} is not after latest balance snapshot "
            f"{snapshot['timestamp']} for entity {body.transaction.entity_id} / {body.transaction.currency}"
        )


def create(body: FullTransactionCreate) -> FullTransactionResponse:
    conn = get_db()
    try:
        _check_snapshot_constraint(conn, body)
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
