import sqlite3

from db import queries
from db.connection import get_db
from models import IncomeCategory, TransactionCreate, TransactionResponse
from models.enums import DividendType, TransactionCategory, TransactionType


class TransactionError(Exception):
    pass


class TransactionNotFound(TransactionError):
    pass


class FKNotFound(TransactionError):
    pass


class TransactionHasDependents(TransactionError):
    pass


class ValidationError(TransactionError):
    pass


def _resolve_fx_fields(body: TransactionCreate) -> TransactionCreate:
    """Auto-populate fx_rate, gross_amount, and net_amount for cross-currency transactions.

    When payment_currency differs from currency and fx_rate is None, resolves it from
    the currencies table. When fx_rate is present, computes gross_amount and net_amount
    if they are not explicitly provided.
    """
    if body.payment_currency is None or body.payment_currency == body.currency:
        return body

    fx_rate = body.fx_rate
    gross_amount = body.gross_amount
    net_amount = body.net_amount

    if fx_rate is None:
        from services.currency_svc import get_rate

        try:
            fx_rate = get_rate(body.currency, body.payment_currency).rate
        except Exception:
            fx_rate = None

    total = body.total_value
    if total is None:
        return body

    if fx_rate is not None:
        if gross_amount is None:
            gross_amount = round(total * fx_rate, 2)
        # net_amount = gross_amount - sum(fees in payment_currency)
        # Fee handling is done in transaction_full_svc which has access to fee data.
        # Here we only compute from what's available.
        if net_amount is None and gross_amount is not None:
            net_amount = gross_amount

    return body.model_copy(
        update={"fx_rate": fx_rate, "gross_amount": gross_amount, "net_amount": net_amount},
    )


def _resolve_fks(conn, body: TransactionCreate) -> None:
    if not queries.get_entity(conn, body.entity_id):
        raise FKNotFound(f"Entity {body.entity_id} not found")
    if not queries.code_exists(conn, body.currency):
        raise FKNotFound(f"Currency '{body.currency}' not found")
    if body.portfolio_asset_id is not None and not queries.get_portfolio_asset(conn, body.portfolio_asset_id):
        raise FKNotFound(f"Portfolio asset {body.portfolio_asset_id} not found")
    if body.payment_currency is not None and not queries.code_exists(conn, body.payment_currency):
        raise FKNotFound(f"Currency '{body.payment_currency}' not found")
    if body.fiscal_exemption_id is not None and not queries.get_fiscal_exemption(conn, body.fiscal_exemption_id):
        raise FKNotFound(f"Fiscal exemption {body.fiscal_exemption_id} not found")
    if body.dividend_currency is not None and not queries.code_exists(conn, body.dividend_currency):
        raise FKNotFound(f"Currency '{body.dividend_currency}' not found")
    if body.dividend_payment_currency is not None and not queries.code_exists(conn, body.dividend_payment_currency):
        raise FKNotFound(f"Currency '{body.dividend_payment_currency}' not found")


def _resolve_investment_fields(body: TransactionCreate) -> tuple[float | None, float | None, float | None]:
    """Resolve quantity, unit_price, total_value — computing whichever is missing from the other two.
    For investment types: if exactly 2 of 3 are provided, computes the third.
    If fewer than 2 are provided, passes through as-is.
    For non-investment types: only computes total_value from quantity*unit_price if missing."""
    qty = body.quantity
    price = body.unit_price
    total = body.total_value

    if body.type not in (TransactionType.INVESTMENT_BUY, TransactionType.INVESTMENT_SELL):
        if total is None and qty is not None and price is not None:
            total = qty * price
        return qty, price, total

    provided = sum(1 for v in (qty, price, total) if v is not None)

    if provided == 3:
        return qty, price, total

    if provided == 2:
        if total is None:
            assert qty is not None and price is not None
            total = qty * price
        elif qty is None:
            assert total is not None and price is not None
            if price == 0:
                return qty, price, total
            qty = total / price
        elif price is None:
            assert total is not None and qty is not None
            if qty == 0:
                return qty, price, total
            price = total / qty

    elif provided < 2 and total is not None:
        # Only total_value provided — default quantity to 1 for cost basis tracking
        qty = 1.0
        price = total

    return qty, price, total


def _to_iso(dt):
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return dt


def _recalculate_adjustments(conn, entity_id: int, currency: str, timestamp: str) -> None:
    next_snapshot = queries.get_next_snapshot(conn, entity_id, currency, timestamp)

    if next_snapshot:
        balance_expected = queries.get_balance_at_date(conn, entity_id, currency, next_snapshot["timestamp"])
        adjustment_amount = next_snapshot["amount"] - balance_expected
        adjustment_ts = next_snapshot["timestamp"][:10] + "T00:00:00"

        existing_adj = queries.get_adjustment_transaction(conn, entity_id, currency, next_snapshot["timestamp"])
        notes = f"Balance adjustment for snapshot at {next_snapshot['timestamp']}"

        if existing_adj:
            queries.update_adjustment_transaction(conn, existing_adj["id"], adjustment_amount, notes)
        else:
            queries.create_adjustment_transaction(conn, entity_id, currency, adjustment_amount, adjustment_ts, notes)


def _ensure_cash_for_buy(conn, entity_id: int, currency: str, timestamp: str, total_value: float) -> None:
    """Ensure sufficient cash exists before an INVESTMENT_BUY.

    Calculates the cash balance at (timestamp - 1 day). If it is insufficient
    to cover the buy, creates or increments a balance snapshot at (timestamp - 1 day)
    with the shortfall amount. This handles registering old investments that were
    not funded by prior transactions in the system.

    If a snapshot already exists at the same entity/currency/timestamp, the shortfall
    is added to its amount instead of creating a duplicate.  Multiple buys on the same
    date share one snapshot, preventing same-timestamp duplicates from silently
    disappearing from get_previous_snapshot (which returns only one row).
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    ts = _dt.fromisoformat(timestamp) if "T" in timestamp else _dt.strptime(timestamp, "%Y-%m-%d")
    snapshot_ts = (ts - _td(days=1)).isoformat()
    balance = queries.get_balance_at_date(conn, entity_id, currency, snapshot_ts)

    if balance >= total_value:
        return

    needed = total_value - balance
    existing = queries.get_snapshot_at_timestamp(conn, entity_id, currency, snapshot_ts)
    if existing:
        merged = existing["amount"] + needed
        queries.update_balance_snapshot(
            conn,
            snapshot_id=existing["id"],
            entity_id=entity_id,
            currency=currency,
            amount=merged,
            timestamp=snapshot_ts,
            notes=f"Auto-created: inferred cash for investment purchases (merged {existing['amount']} + {needed})",
        )
    else:
        queries.create_balance_snapshot(
            conn,
            entity_id=entity_id,
            currency=currency,
            amount=needed,
            timestamp=snapshot_ts,
            notes=f"Auto-created: inferred cash for investment purchase of {total_value}",
        )


def create(body: TransactionCreate, conn: sqlite3.Connection | None = None) -> TransactionResponse:
    if conn is None:
        conn = get_db()
        should_commit = True
    else:
        should_commit = False
    _resolve_fks(conn, body)
    qty, price, total_value = _resolve_investment_fields(body)
    if total_value is not None:
        body = body.model_copy(update={"total_value": total_value})
    body = _resolve_fx_fields(body)
    total_value = body.total_value or total_value
    tx_id = queries.create_transaction(
        conn,
        timestamp=_to_iso(body.timestamp),
        type_=body.type.value,
        entity_id=body.entity_id,
        currency=body.currency,
        total_value=total_value,
        transaction_category=body.transaction_category.value if body.transaction_category else None,
        income_category=body.income_category.value if body.income_category else None,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=qty,
        unit_price=price,
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

    if body.type == TransactionType.INVESTMENT_BUY and total_value is not None:
        _ensure_cash_for_buy(conn, body.entity_id, body.currency, _to_iso(body.timestamp), total_value)

    if body.type != TransactionType.BALANCE_ADJUSTMENT:
        _recalculate_adjustments(conn, body.entity_id, body.currency, _to_iso(body.timestamp))

    if should_commit:
        conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        transaction_category=body.transaction_category,
        income_category=body.income_category,
        entity_id=body.entity_id,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=qty,
        unit_price=price,
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


def get_full(tx_id: int) -> dict:
    conn = get_db()
    row = queries.get_transaction(conn, tx_id)
    if row is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")

    fees = queries.get_fees_by_transaction(conn, tx_id)
    taxes = queries.get_taxes_by_transaction(conn, tx_id)

    return {
        "transaction": _row_to_response(row),
        "fees": fees,
        "taxes": taxes,
    }


def list_all(
    start_date: str | None = None,
    end_date: str | None = None,
    type_filter: str | None = None,
    entity_id: int | None = None,
    currency: str | None = None,
) -> list[TransactionResponse]:
    conn = get_db()
    rows = queries.get_all_transactions(
        conn,
        start_date=start_date,
        end_date=end_date,
        type_filter=type_filter,
        entity_id=entity_id,
        currency=currency,
    )
    return [_row_to_response(r) for r in rows]


def update(tx_id: int, body: TransactionCreate, conn: sqlite3.Connection | None = None) -> TransactionResponse:
    if conn is None:
        conn = get_db()
        should_commit = True
    else:
        should_commit = False
    existing = queries.get_transaction(conn, tx_id)
    if existing is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")

    old_entity_id = existing["entity_id"]
    old_currency = existing["currency"]
    old_timestamp = existing["timestamp"]

    _resolve_fks(conn, body)
    qty, price, total_value = _resolve_investment_fields(body)
    if total_value is not None:
        body = body.model_copy(update={"total_value": total_value})
    body = _resolve_fx_fields(body)
    total_value = body.total_value or total_value
    queries.update_transaction(
        conn,
        tx_id,
        timestamp=_to_iso(body.timestamp),
        type_=body.type.value,
        entity_id=body.entity_id,
        currency=body.currency,
        total_value=total_value,
        transaction_category=body.transaction_category.value if body.transaction_category else None,
        income_category=body.income_category.value if body.income_category else None,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=qty,
        unit_price=price,
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

    if body.type != TransactionType.BALANCE_ADJUSTMENT:
        _recalculate_adjustments(conn, body.entity_id, body.currency, _to_iso(body.timestamp))

        if old_entity_id != body.entity_id or old_currency != body.currency or old_timestamp != _to_iso(body.timestamp):
            _recalculate_adjustments(conn, old_entity_id, old_currency, old_timestamp)

    if should_commit:
        conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        transaction_category=body.transaction_category,
        income_category=body.income_category,
        entity_id=body.entity_id,
        portfolio_asset_id=body.portfolio_asset_id,
        quantity=qty,
        unit_price=price,
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
    if queries.transaction_has_dependents(conn, tx_id):
        raise TransactionHasDependents(f"Transaction {tx_id} has fees, taxes, or schedules referencing it")

    entity_id = existing["entity_id"]
    currency = existing["currency"]
    timestamp = existing["timestamp"]

    queries.delete_transaction(conn, tx_id)

    if existing["type"] != "BALANCE_ADJUSTMENT":
        _recalculate_adjustments(conn, entity_id, currency, timestamp)

    conn.commit()


def _row_to_response(row: dict) -> TransactionResponse:
    return TransactionResponse(
        id=row["id"],
        timestamp=row["timestamp"],
        type=TransactionType(row["type"]),
        transaction_category=TransactionCategory(row["transaction_category"]) if row["transaction_category"] else None,
        income_category=IncomeCategory(row["income_category"]) if row.get("income_category") else None,
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
