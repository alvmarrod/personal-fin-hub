from datetime import datetime

from db.connection import get_db
from db import queries
from models import TransactionCreate, TransactionResponse
from models.enums import DividendType, TransactionCategory, TransactionType


class TransactionError(Exception):
    pass


class TransactionNotFound(TransactionError):
    pass


class FKNotFound(TransactionError):
    pass


def _resolve_fks(conn, body: TransactionCreate) -> None:
    if not queries.get_entity(conn, body.entity_id):
        raise FKNotFound(f"Entity {body.entity_id} not found")
    if not queries.code_exists(conn, body.currency):
        raise FKNotFound(f"Currency '{body.currency}' not found")
    if body.portfolio_asset_id is not None:
        if not queries.get_portfolio_asset(conn, body.portfolio_asset_id):
            raise FKNotFound(f"Portfolio asset {body.portfolio_asset_id} not found")
    if body.payment_currency is not None:
        if not queries.code_exists(conn, body.payment_currency):
            raise FKNotFound(f"Currency '{body.payment_currency}' not found")
    if body.fiscal_exemption_id is not None:
        if not queries.get_fiscal_exemption(conn, body.fiscal_exemption_id):
            raise FKNotFound(f"Fiscal exemption {body.fiscal_exemption_id} not found")
    if body.dividend_currency is not None:
        if not queries.code_exists(conn, body.dividend_currency):
            raise FKNotFound(f"Currency '{body.dividend_currency}' not found")
    if body.dividend_payment_currency is not None:
        if not queries.code_exists(conn, body.dividend_payment_currency):
            raise FKNotFound(f"Currency '{body.dividend_payment_currency}' not found")


def _compute_total_value(body: TransactionCreate) -> float | None:
    if body.total_value is not None:
        return body.total_value
    if body.quantity is not None and body.unit_price is not None:
        return body.quantity * body.unit_price
    return None


def _to_iso(dt):
    return dt.isoformat() if hasattr(dt, 'isoformat') else dt


def create(body: TransactionCreate) -> TransactionResponse:
    conn = get_db()
    _resolve_fks(conn, body)
    total_value = _compute_total_value(body)
    tx_id = queries.create_transaction(
        conn,
        timestamp=_to_iso(body.timestamp),
        type_=body.type.value,
        entity_id=body.entity_id,
        currency=body.currency,
        total_value=total_value,
        transaction_category=body.transaction_category.value if body.transaction_category else None,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        gross_amount=body.gross_amount,
        net_amount=body.net_amount,
        payment_currency=body.payment_currency,
        fx_rate=body.fx_rate,
        settlement_date=_to_iso(body.settlement_date) if body.settlement_date else None,
        fiscal_exemption_id=body.fiscal_exemption_id,
        dividend_type=body.dividend_type.value if body.dividend_type else None,
        record_date=_to_iso(body.record_date) if body.record_date else None,
        payment_date=_to_iso(body.payment_date) if body.payment_date else None,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
    )
    conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        transaction_category=body.transaction_category,
        entity_id=body.entity_id,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        currency=body.currency,
        total_value=total_value,
        gross_amount=body.gross_amount,
        net_amount=body.net_amount,
        payment_currency=body.payment_currency,
        fx_rate=body.fx_rate,
        settlement_date=body.settlement_date,
        fiscal_exemption_id=body.fiscal_exemption_id,
        dividend_type=body.dividend_type,
        record_date=body.record_date,
        payment_date=body.payment_date,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
    )


def get(tx_id: int) -> TransactionResponse:
    conn = get_db()
    row = queries.get_transaction(conn, tx_id)
    if row is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")
    return _row_to_response(row)


def list_all() -> list[TransactionResponse]:
    conn = get_db()
    rows = queries.get_all_transactions(conn)
    return [_row_to_response(r) for r in rows]


def update(tx_id: int, body: TransactionCreate) -> TransactionResponse:
    conn = get_db()
    existing = queries.get_transaction(conn, tx_id)
    if existing is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")
    _resolve_fks(conn, body)
    total_value = _compute_total_value(body)
    queries.update_transaction(
        conn,
        tx_id,
        timestamp=_to_iso(body.timestamp),
        type_=body.type.value,
        entity_id=body.entity_id,
        currency=body.currency,
        total_value=total_value,
        transaction_category=body.transaction_category.value if body.transaction_category else None,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        gross_amount=body.gross_amount,
        net_amount=body.net_amount,
        payment_currency=body.payment_currency,
        fx_rate=body.fx_rate,
        settlement_date=_to_iso(body.settlement_date) if body.settlement_date else None,
        fiscal_exemption_id=body.fiscal_exemption_id,
        dividend_type=body.dividend_type.value if body.dividend_type else None,
        record_date=_to_iso(body.record_date) if body.record_date else None,
        payment_date=_to_iso(body.payment_date) if body.payment_date else None,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
    )
    conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        transaction_category=body.transaction_category,
        entity_id=body.entity_id,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        currency=body.currency,
        total_value=total_value,
        gross_amount=body.gross_amount,
        net_amount=body.net_amount,
        payment_currency=body.payment_currency,
        fx_rate=body.fx_rate,
        settlement_date=body.settlement_date,
        fiscal_exemption_id=body.fiscal_exemption_id,
        dividend_type=body.dividend_type,
        record_date=body.record_date,
        payment_date=body.payment_date,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
    )


def delete(tx_id: int) -> None:
    conn = get_db()
    existing = queries.get_transaction(conn, tx_id)
    if existing is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")
    queries.delete_transaction(conn, tx_id)
    conn.commit()


def _row_to_response(row: dict) -> TransactionResponse:
    return TransactionResponse(
        id=row["id"],
        timestamp=row["timestamp"],
        type=TransactionType(row["type"]),
        transaction_category=TransactionCategory(row["transaction_category"]) if row["transaction_category"] else None,
        entity_id=row["entity_id"],
        portfolio_asset_id=row["portfolio_asset_id"],
        quantity=row["quantity"],
        unit_price=row["unit_price"],
        currency=row["currency"],
        total_value=row["total_value"],
        gross_amount=row["gross_amount"],
        net_amount=row["net_amount"],
        payment_currency=row["payment_currency"],
        fx_rate=row["fx_rate"],
        settlement_date=row["settlement_date"],
        fiscal_exemption_id=row["fiscal_exemption_id"],
        dividend_type=DividendType(row["dividend_type"]) if row["dividend_type"] else None,
        record_date=row["record_date"],
        payment_date=row["payment_date"],
        dividend_currency=row["dividend_currency"],
        dividend_payment_currency=row["dividend_payment_currency"],
        dividend_fx_rate=row["dividend_fx_rate"],
        notes=row["notes"],
    )
