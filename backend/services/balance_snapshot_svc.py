from db.connection import get_db
from db import queries
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
    return dt.isoformat() if hasattr(dt, 'isoformat') else dt


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
    queries.delete_balance_snapshot(conn, snapshot_id)
    conn.commit()
