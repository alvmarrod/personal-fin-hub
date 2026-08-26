import sqlite3

from db import queries
from db.connection import get_db
from models import IncomeCategory, TransactionCreate, TransactionResponse
from models.enums import BalanceMode, DividendType, InvestmentTransactionCategory, TransactionType


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


SPEND_TYPES = frozenset({TransactionType.INVESTMENT_BUY, TransactionType.MONEY_OUT, TransactionType.TRANSFER_OUT})


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
        # computed_balance excludes the snapshot's own adjustment (avoid circularity)
        balance_expected = queries.get_balance_at_date(
            conn,
            entity_id,
            currency,
            next_snapshot["timestamp"],
            exclude_adjustment_snapshot_id=next_snapshot["id"],
        )
        adjustment_amount = next_snapshot["amount"] - balance_expected
        adjustment_ts = queries.adjustment_timestamp(next_snapshot["timestamp"])

        existing_adj = queries.get_adjustment_transaction(conn, entity_id, currency, next_snapshot["id"])
        notes = f"Balance adjustment for snapshot at {next_snapshot['timestamp']}"

        if existing_adj:
            queries.update_adjustment_transaction(conn, existing_adj["id"], adjustment_amount, notes)
        else:
            queries.create_adjustment_transaction(
                conn, entity_id, currency, adjustment_amount, adjustment_ts, next_snapshot["id"], notes
            )


def reconcile_after_fee_change(conn, transaction_id: int) -> None:
    """Refresh snapshot adjustments after a fee/tax CRUD operation.

    Recalculates the adjustment for the parent transaction's pair and, when
    the entity has a ``main_currency`` that differs, also for the main
    pocket — fees always charge the main pocket.  When fee drains drive the
    main pocket negative and no prior snapshot anchors it, an inferred-cash
    injection is created/refreshed and linked to the parent spends.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    tx = queries.get_transaction(conn, transaction_id)
    if tx is None:
        return
    if tx["type"] == "BALANCE_ADJUSTMENT":
        return

    _recalculate_adjustments(conn, tx["entity_id"], tx["currency"], tx["timestamp"])

    entity = queries.get_entity(conn, tx["entity_id"])
    if not entity or not entity.get("main_currency"):
        return
    main_currency = entity["main_currency"]
    if main_currency == tx["currency"]:
        return

    _recalculate_adjustments(conn, tx["entity_id"], main_currency, tx["timestamp"])

    # Fee-driven injection on the main pocket
    ts = _dt.fromisoformat(tx["timestamp"]) if "T" in tx["timestamp"] else _dt.strptime(tx["timestamp"], "%Y-%m-%d")
    injection_ts = (ts - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"

    anchored = queries.get_previous_snapshot(conn, tx["entity_id"], main_currency, injection_ts) is not None
    if anchored:
        return

    balance = queries.get_balance_at_date(
        conn,
        tx["entity_id"],
        main_currency,
        tx["timestamp"],
    )
    existing = queries.get_injected_adjustment_at(conn, tx["entity_id"], main_currency, injection_ts)
    if balance >= 0:
        if existing:
            queries.delete_transaction(conn, existing["id"])
        return

    needed = -balance
    notes = "Inferred cash for investment purchases"
    if existing:
        queries.update_adjustment_transaction(conn, existing["id"], needed, notes)
    else:
        adj_id = queries.create_adjustment_transaction(
            conn,
            tx["entity_id"],
            main_currency,
            needed,
            injection_ts,
            None,
            notes,
        )
        # Link to parent spends in the main currency
        placeholders = ", ".join("?" for _ in SPEND_TYPES)
        spend_types_values = [s.value for s in SPEND_TYPES]
        spends = conn.execute(
            f"SELECT id FROM transactions "
            f"WHERE entity_id = ? AND currency = ? AND type IN ({placeholders}) "
            f"AND timestamp >= ? AND timestamp < ?",
            (tx["entity_id"], main_currency, *spend_types_values, injection_ts[:10], injection_ts[:10]),
        ).fetchall()
        for sp in spends:
            queries.link_adjustment_to_transaction(conn, adj_id, sp["id"])


def _ensure_cash_for_spend(
    conn,
    entity_id: int,
    currency: str,
    timestamp: str,
    total_value: float,
    mode=None,
    exclude_transaction_id: int | None = None,
) -> None:
    """Ensure a spend does not silently drive its pair below zero.

    If the running cash balance just before the spend is insufficient and no
    prior balance snapshot anchors the pair, the shortfall is injected as a
    standalone BALANCE_ADJUSTMENT ("inferred cash") at (timestamp - 1 day)
    23:59:59. When a prior snapshot exists the default is to debit the known
    balance instead — letting it go negative if that reflects reality (Tier 5
    Reconciliation Model). ``mode`` overrides the default: 'debit' never
    injects; 'inject' forces the shortfall injection even when anchored.
    Multiple spends on the same date merge into a single injected adjustment.
    ``exclude_transaction_id`` measures without the row being edited (update
    flow, where the row already carries its new values).
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    if mode == BalanceMode.DEBIT:
        return

    ts = _dt.fromisoformat(timestamp) if "T" in timestamp else _dt.strptime(timestamp, "%Y-%m-%d")
    injection_ts = (ts - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"

    anchored = queries.get_previous_snapshot(conn, entity_id, currency, injection_ts) is not None
    if anchored and mode != BalanceMode.INJECT:
        return

    # Measured at the spend's own timestamp (the row is inserted after this
    # check), so same-day earlier spends are part of the running balance.
    balance = queries.get_balance_at_date(
        conn, entity_id, currency, timestamp, exclude_transaction_id=exclude_transaction_id
    )
    if balance >= total_value:
        return

    needed = total_value - balance
    notes = "Inferred cash for investment purchases"
    existing = queries.get_injected_adjustment_at(conn, entity_id, currency, injection_ts)
    if existing:
        queries.update_adjustment_transaction(conn, existing["id"], (existing["total_value"] or 0.0) + needed, notes)
    else:
        queries.create_adjustment_transaction(conn, entity_id, currency, needed, injection_ts, None, notes)


def _link_injection(conn, entity_id: int, currency: str, timestamp: str, spend_id: int) -> None:
    """Attach a spend to the injected adjustment at (timestamp - 1 day) 23:59:59.

    Runs after the spend row exists, so both freshly created injections and
    same-day merges into an existing one end up linked (Attachment Model).
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    ts = _dt.fromisoformat(timestamp) if "T" in timestamp else _dt.strptime(timestamp, "%Y-%m-%d")
    injection_ts = (ts - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"
    existing = queries.get_injected_adjustment_at(conn, entity_id, currency, injection_ts)
    if existing:
        queries.link_adjustment_to_transaction(conn, existing["id"], spend_id)


def _required_injection_for_day(
    conn,
    entity_id: int,
    currency: str,
    spend_day: str,
    injected_adj_id: int | None = None,
    exclude_transaction_id: int | None = None,
) -> float:
    """Cash top-up needed so the day's spends never drive the pair negative.

    Walks the day chronologically from the opening balance (excluding the
    given injected adjustment itself) tracking the deepest cumulative deficit.
    ``exclude_transaction_id`` drops one row from the walk (the spend being
    edited, which re-enters through the ensure step).
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    d = _dt.strptime(spend_day, "%Y-%m-%d")
    day_end = (d + _td(days=1)).strftime("%Y-%m-%dT00:00:00")
    # Strict opening (timestamp < day start) so rows sitting exactly at the
    # day boundary are counted once — in the walk below, not here.
    opening = queries.get_balance_at_date(
        conn,
        entity_id,
        currency,
        spend_day + "T00:00:00",
        exclude_adjustment_id=injected_adj_id,
        exclude_transaction_id=exclude_transaction_id,
        inclusive_end=False,
    )
    running = opening
    required = 0.0
    for tx in queries.get_transactions_between(
        conn, entity_id, currency, spend_day + "T00:00:00", day_end, exclude_transaction_id=exclude_transaction_id
    ):
        if tx["type"] in ("MONEY_OUT", "INVESTMENT_BUY", "TRANSFER_OUT"):
            running -= tx["total_value"] or 0.0
            required = max(required, -running)
        elif tx["type"] in ("INCOME", "INVESTMENT_SELL", "TRANSFER_IN"):
            running += tx["total_value"] or 0.0
    return round(required, 2)


def _refresh_injection(conn, adjustment_id: int, exclude_transaction_id: int | None = None) -> None:
    """Recompute an attached injection from its linked spends (Lifecycle).

    Raised or lowered to the combined shortfall of its links; deleted together
    with its links when no link remains or no shortfall exists. Snapshot-linked
    adjustments are never touched here.
    """
    adj = queries.get_transaction(conn, adjustment_id)
    if adj is None or adj["type"] != "BALANCE_ADJUSTMENT" or adj["balance_snapshot_id"] is not None:
        return

    link_ids = queries.get_attached_transaction_ids(conn, adjustment_id)
    if not link_ids:
        queries.remove_links_for_transaction(conn, adjustment_id)
        queries.delete_injection_if_unlinked(conn, adjustment_id)
        return

    from datetime import datetime as _dt
    from datetime import timedelta as _td

    d = _dt.strptime(adj["timestamp"][:10], "%Y-%m-%d")
    spend_day = (d + _td(days=1)).strftime("%Y-%m-%d")
    required = _required_injection_for_day(
        conn, adj["entity_id"], adj["currency"], spend_day, adjustment_id, exclude_transaction_id
    )

    if required <= 0:
        queries.remove_links_for_transaction(conn, adjustment_id)
        queries.delete_injection_if_unlinked(conn, adjustment_id)
    else:
        queries.update_adjustment_transaction(conn, adjustment_id, required, "Inferred cash for investment purchases")


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
    if body.type in SPEND_TYPES and total_value is not None:
        # Before inserting the row so the shortfall measurement excludes it,
        # including spends recorded earlier on the same date.
        _ensure_cash_for_spend(
            conn, body.entity_id, body.currency, _to_iso(body.timestamp), total_value, mode=body.cash_handling
        )

    tx_id = queries.create_transaction(
        conn,
        timestamp=_to_iso(body.timestamp),
        type_=body.type.value,
        entity_id=body.entity_id,
        currency=body.currency,
        total_value=total_value,
        investment_transaction_category=body.investment_transaction_category.value
        if body.investment_transaction_category
        else None,
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
        cash_handling=body.cash_handling.value if body.cash_handling else None,
    )

    if body.type in SPEND_TYPES:
        _link_injection(conn, body.entity_id, body.currency, _to_iso(body.timestamp), tx_id)

    if body.type != TransactionType.BALANCE_ADJUSTMENT:
        _recalculate_adjustments(conn, body.entity_id, body.currency, _to_iso(body.timestamp))

    row = queries.get_transaction(conn, tx_id)
    fiscal_rule = row["fiscal_rule"] if row else None

    if should_commit:
        conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        investment_transaction_category=body.investment_transaction_category,
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
        fiscal_rule=fiscal_rule,
        dividend_type=body.dividend_type,
        record_date=body.record_date,
        payment_date=body.payment_date,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
        cash_handling=body.cash_handling,
    )


def get(tx_id: int, conn: sqlite3.Connection | None = None) -> TransactionResponse:
    if conn is None:
        conn = get_db()
    row = queries.get_transaction(conn, tx_id)
    if row is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")
    return _row_to_response(row, conn)


def get_full(tx_id: int) -> dict:
    conn = get_db()
    row = queries.get_transaction(conn, tx_id)
    if row is None:
        raise TransactionNotFound(f"Transaction {tx_id} not found")

    fees = queries.get_fees_by_transaction(conn, tx_id)
    taxes = queries.get_taxes_by_transaction(conn, tx_id)

    return {
        "transaction": _row_to_response(row, conn),
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
    return [_row_to_response(r, conn) for r in rows]


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
    # An omitted cash_handling preserves the persisted cash-handling record
    # (edit payloads from clients that do not know the field must not erase it).
    # An explicitly sent null clears the record, returning the spend to Auto.
    existing_cash_handling = existing.get("cash_handling")
    if "cash_handling" in body.model_fields_set:
        effective_cash_handling = body.cash_handling.value if body.cash_handling else None
    else:
        effective_cash_handling = existing_cash_handling
    old_was_spend = existing["type"] in SPEND_TYPES
    linked_adjs = queries.get_adjustments_linked_to_transaction(conn, tx_id) if old_was_spend else []

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
        investment_transaction_category=body.investment_transaction_category.value
        if body.investment_transaction_category
        else None,
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
        cash_handling=effective_cash_handling,
    )

    # Edit-time injection lifecycle: detach the spend from any previously
    # attached injection, then refresh that injection against its remaining
    # spends (raised/lowered/removed). The edited row is excluded from the
    # recomputation — it re-enters through the ensure step below.
    if old_was_spend:
        queries.remove_links_for_transaction(conn, tx_id)
        for adj in linked_adjs:
            _refresh_injection(conn, adj["id"], exclude_transaction_id=tx_id)

    if body.type.value in SPEND_TYPES and total_value is not None:
        _ensure_cash_for_spend(
            conn,
            body.entity_id,
            body.currency,
            _to_iso(body.timestamp),
            total_value,
            mode=effective_cash_handling,
            exclude_transaction_id=tx_id,
        )
        _link_injection(conn, body.entity_id, body.currency, _to_iso(body.timestamp), tx_id)

    if body.type != TransactionType.BALANCE_ADJUSTMENT:
        _recalculate_adjustments(conn, body.entity_id, body.currency, _to_iso(body.timestamp))

        if old_entity_id != body.entity_id or old_currency != body.currency or old_timestamp != _to_iso(body.timestamp):
            _recalculate_adjustments(conn, old_entity_id, old_currency, old_timestamp)

    row = queries.get_transaction(conn, tx_id)
    fiscal_rule = row["fiscal_rule"] if row else None

    if should_commit:
        conn.commit()
    return TransactionResponse(
        id=tx_id,
        timestamp=body.timestamp,
        type=body.type,
        investment_transaction_category=body.investment_transaction_category,
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
        fiscal_rule=fiscal_rule,
        dividend_type=body.dividend_type,
        record_date=body.record_date,
        payment_date=body.payment_date,
        dividend_currency=body.dividend_currency,
        dividend_payment_currency=body.dividend_payment_currency,
        dividend_fx_rate=body.dividend_fx_rate,
        notes=body.notes,
        cash_handling=BalanceMode(effective_cash_handling) if effective_cash_handling else None,
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

    # Capture attached injections before dropping the spend's link rows, then
    # delete any injection left without links (Adjustment Lifecycle).
    was_spend = existing["type"] in SPEND_TYPES
    attached = queries.get_adjustments_linked_to_transaction(conn, tx_id) if was_spend else []

    queries.remove_links_for_transaction(conn, tx_id)
    queries.delete_transaction(conn, tx_id)

    for adj in attached:
        queries.delete_injection_if_unlinked(conn, adj["id"])

    if existing["type"] != "BALANCE_ADJUSTMENT":
        _recalculate_adjustments(conn, entity_id, currency, timestamp)

    conn.commit()


def _resolve_effective_cash_handling(conn: sqlite3.Connection, row: dict) -> BalanceMode | None:
    """Effective cash-handling policy of a spend row.

    An explicit ``cash_handling`` value wins. Otherwise Auto is resolved the
    same way ``_ensure_cash_for_spend`` resolves it at record time: a pair
    anchored by a prior snapshot debits (no injection); an unanchored pair
    injects inferred cash when short. Non-spend rows have no policy.
    """
    if row["type"] not in SPEND_TYPES:
        return None
    stored = row.get("cash_handling")
    if stored:
        return BalanceMode(stored)
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    ts = _dt.fromisoformat(row["timestamp"])
    injection_ts = (ts - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"
    anchored = queries.get_previous_snapshot(conn, row["entity_id"], row["currency"], injection_ts) is not None
    return BalanceMode.DEBIT if anchored else BalanceMode.INJECT


def _row_to_response(row: dict, conn: sqlite3.Connection | None = None) -> TransactionResponse:
    return TransactionResponse(
        id=row["id"],
        timestamp=row["timestamp"],
        type=TransactionType(row["type"]),
        investment_transaction_category=InvestmentTransactionCategory(row["investment_transaction_category"])
        if row["investment_transaction_category"]
        else None,
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
        fiscal_rule=row["fiscal_rule"],
        dividend_type=DividendType(row["dividend_type"]) if row["dividend_type"] else None,
        record_date=row["record_date"],
        payment_date=row["payment_date"],
        dividend_currency=row["dividend_currency"],
        dividend_payment_currency=row["dividend_payment_currency"],
        dividend_fx_rate=row["dividend_fx_rate"],
        notes=row["notes"],
        cash_handling=BalanceMode(row["cash_handling"]) if row.get("cash_handling") else None,
        cash_handling_effective=(_resolve_effective_cash_handling(conn, row) if conn is not None else None),
        attached_transaction_ids=(
            queries.get_attached_transaction_ids(conn, row["id"])
            if conn is not None and row["type"] == "BALANCE_ADJUSTMENT"
            else None
        ),
    )
