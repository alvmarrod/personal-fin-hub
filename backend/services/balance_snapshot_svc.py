from db import queries
from db.connection import get_db
from models import BalanceSnapshotCreate, BalanceSnapshotResponse


class BalanceSnapshotError(Exception):
    pass


class BalanceSnapshotNotFound(BalanceSnapshotError):
    pass


class BalanceSnapshotConflict(BalanceSnapshotError):
    pass


class EntityNotFound(BalanceSnapshotError):
    pass


class CurrencyNotFound(BalanceSnapshotError):
    pass


def _to_iso(dt):
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return dt


def _resolve_fk(conn, body: BalanceSnapshotCreate) -> None:
    if not queries.get_entity(conn, body.entity_id):
        raise EntityNotFound(f"Entity {body.entity_id} not found")
    if not queries.code_exists(conn, body.currency):
        raise CurrencyNotFound(f"Currency '{body.currency}' not found")


def _check_conflicts(conn, body: BalanceSnapshotCreate) -> None:
    ts = _to_iso(body.timestamp)
    if queries.has_transactions_on_or_after(conn, body.entity_id, body.currency, ts):
        raise BalanceSnapshotConflict(
            f"Cannot create snapshot: transactions exist with timestamp >= {ts} "
            f"for entity {body.entity_id} / {body.currency}"
        )
    date_only = ts[:10] if isinstance(ts, str) else str(ts)[:10]
    if queries.has_schedules_on_or_before(conn, body.entity_id, body.currency, date_only):
        raise BalanceSnapshotConflict(
            f"Cannot create snapshot: schedules exist with start_date <= {date_only} "
            f"for entity {body.entity_id} / {body.currency}"
        )


def _create_or_update_adjustment(
    conn, entity_id: int, currency: str, snapshot_id: int, snapshot_timestamp: str, target_amount: float
) -> None:
    adjustment_ts = queries.adjustment_timestamp(snapshot_timestamp)

    existing_adj = queries.get_adjustment_transaction(conn, entity_id, currency, snapshot_id)

    balance_expected = queries.get_balance_at_date(
        conn, entity_id, currency, snapshot_timestamp, exclude_adjustment_snapshot_id=snapshot_id
    )
    adjustment_amount = target_amount - balance_expected

    notes = f"Balance adjustment for snapshot at {snapshot_timestamp}"

    if existing_adj:
        queries.update_adjustment_transaction(conn, existing_adj["id"], adjustment_amount, notes)
    else:
        queries.create_adjustment_transaction(
            conn, entity_id, currency, adjustment_amount, adjustment_ts, snapshot_id, notes
        )


def _delete_adjustment(conn, entity_id: int, currency: str, snapshot_id: int) -> None:
    queries.delete_adjustment_transaction(conn, entity_id, currency, snapshot_id)


def create(body: BalanceSnapshotCreate) -> BalanceSnapshotResponse:
    conn = get_db()
    _resolve_fk(conn, body)
    _check_conflicts(conn, body)
    ts = _to_iso(body.timestamp)
    snapshot_id = queries.create_balance_snapshot(
        conn,
        entity_id=body.entity_id,
        currency=body.currency,
        amount=body.amount,
        timestamp=ts,
        notes=body.notes,
    )

    prev_snapshot = queries.get_previous_snapshot(conn, body.entity_id, body.currency, ts)
    if prev_snapshot:
        _create_or_update_adjustment(conn, body.entity_id, body.currency, snapshot_id, ts, body.amount)

    conn.commit()
    return BalanceSnapshotResponse(
        id=snapshot_id,
        entity_id=body.entity_id,
        currency=body.currency,
        amount=body.amount,
        timestamp=body.timestamp,
        notes=body.notes,
    )


def get(snapshot_id: int) -> BalanceSnapshotResponse:
    conn = get_db()
    row = queries.get_balance_snapshot(conn, snapshot_id)
    if row is None:
        raise BalanceSnapshotNotFound(f"Balance snapshot {snapshot_id} not found")
    return BalanceSnapshotResponse(
        id=row["id"],
        entity_id=row["entity_id"],
        currency=row["currency"],
        amount=row["amount"],
        timestamp=row["timestamp"],
        notes=row["notes"],
    )


def list_all(entity_id: int | None = None, currency: str | None = None) -> list[BalanceSnapshotResponse]:
    conn = get_db()
    rows = queries.get_all_balance_snapshots(conn)
    result = [
        BalanceSnapshotResponse(
            id=r["id"],
            entity_id=r["entity_id"],
            currency=r["currency"],
            amount=r["amount"],
            timestamp=r["timestamp"],
            notes=r["notes"],
        )
        for r in rows
    ]
    if entity_id is not None:
        result = [r for r in result if r.entity_id == entity_id]
    if currency is not None:
        result = [r for r in result if r.currency == currency]
    return result


def update(snapshot_id: int, body: BalanceSnapshotCreate) -> BalanceSnapshotResponse:
    conn = get_db()
    existing = queries.get_balance_snapshot(conn, snapshot_id)
    if existing is None:
        raise BalanceSnapshotNotFound(f"Balance snapshot {snapshot_id} not found")
    _resolve_fk(conn, body)
    ts = _to_iso(body.timestamp)

    timestamp_changed = existing["timestamp"] != ts
    amount_changed = existing["amount"] != body.amount

    if timestamp_changed or amount_changed:
        _delete_adjustment(conn, existing["entity_id"], existing["currency"], snapshot_id)

        prev_snapshot = queries.get_previous_snapshot(conn, body.entity_id, body.currency, ts)
        if prev_snapshot:
            _create_or_update_adjustment(conn, body.entity_id, body.currency, snapshot_id, ts, body.amount)

    queries.update_balance_snapshot(
        conn,
        snapshot_id,
        entity_id=body.entity_id,
        currency=body.currency,
        amount=body.amount,
        timestamp=ts,
        notes=body.notes,
    )
    conn.commit()
    return BalanceSnapshotResponse(
        id=snapshot_id,
        entity_id=body.entity_id,
        currency=body.currency,
        amount=body.amount,
        timestamp=body.timestamp,
        notes=body.notes,
    )


def delete(snapshot_id: int) -> None:
    conn = get_db()
    existing = queries.get_balance_snapshot(conn, snapshot_id)
    if existing is None:
        raise BalanceSnapshotNotFound(f"Balance snapshot {snapshot_id} not found")

    _delete_adjustment(conn, existing["entity_id"], existing["currency"], existing["id"])

    queries.delete_balance_snapshot(conn, snapshot_id)
    conn.commit()
