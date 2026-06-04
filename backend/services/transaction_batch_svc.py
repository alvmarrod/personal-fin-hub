from db.connection import get_db
from models import BatchCreate, BatchResponse
from services.transaction_svc import FKNotFound, create as create_transaction


class BatchError(Exception):
    pass


def create(body: BatchCreate) -> BatchResponse:
    conn = get_db()
    try:
        transactions = []
        for tx in body.transactions:
            result = create_transaction(tx, conn=conn)
            transactions.append(result)
        conn.commit()
        return BatchResponse(transactions=transactions)
    except FKNotFound:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
