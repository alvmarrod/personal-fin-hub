from datetime import UTC, datetime, timedelta

from db import queries
from db.connection import get_db
from models import BalanceSnapshotCreate, BalanceSnapshotResponse

# A snapshot observed "now" can arrive a few seconds ahead of the server clock.
_FUTURE_TOLERANCE = timedelta(seconds=60)


class BalanceSnapshotError(Exception):
    pass


class BalanceSnapshotNotFound(BalanceSnapshotError):
    pass


class BalanceSnapshotFuture(BalanceSnapshotError):
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


def _reject_future(timestamp: str) -> None:
    """A snapshot is an observed truth, so it cannot be dated in the future."""
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    if moment > datetime.now(UTC) + _FUTURE_TOLERANCE:
        raise BalanceSnapshotFuture(f"Cannot record a snapshot in the future: {timestamp}")


def _recalculate_next_snapshot(conn, entity_id: int, currency: str, timestamp: str) -> None:
    """Refresh the adjustment of the snapshot that follows ``timestamp``.

    Inserting, moving or deleting a snapshot changes the anchor of the next one
    for that pocket. One level is enough: every later snapshot anchors on the
    one after it, not on this one.
    """
    from services.transaction_svc import _recalculate_adjustments

    _recalculate_adjustments(conn, entity_id, currency, timestamp)


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
    ts = _to_iso(body.timestamp)
    _reject_future(ts)

    # A snapshot is the truth at its instant: re-recording the same instant
    # replaces the amount instead of leaving two anchors a tie-break away.
    existing = queries.get_snapshot_at_timestamp(conn, body.entity_id, body.currency, ts)
    if existing:
        snapshot_id = existing["id"]
        queries.update_balance_snapshot(
            conn,
            snapshot_id,
            entity_id=body.entity_id,
            currency=body.currency,
            amount=body.amount,
            timestamp=ts,
            notes=body.notes,
        )
    else:
        snapshot_id = queries.create_balance_snapshot(
            conn,
            entity_id=body.entity_id,
            currency=body.currency,
            amount=body.amount,
            timestamp=ts,
            notes=body.notes,
        )

    _create_or_update_adjustment(conn, body.entity_id, body.currency, snapshot_id, ts, body.amount)
    _recalculate_next_snapshot(conn, body.entity_id, body.currency, ts)

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
    _reject_future(ts)

    other = queries.get_snapshot_at_timestamp(conn, body.entity_id, body.currency, ts)
    if other and other["id"] != snapshot_id:
        raise BalanceSnapshotError(f"A balance snapshot already exists at {ts}")

    timestamp_changed = existing["timestamp"] != ts
    amount_changed = existing["amount"] != body.amount

    if timestamp_changed or amount_changed:
        _delete_adjustment(conn, existing["entity_id"], existing["currency"], snapshot_id)

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

    # Both positions can have a following snapshot whose anchor changed.
    _recalculate_next_snapshot(conn, body.entity_id, body.currency, ts)
    if (existing["entity_id"], existing["currency"], existing["timestamp"]) != (
        body.entity_id,
        body.currency,
        ts,
    ):
        _recalculate_next_snapshot(conn, existing["entity_id"], existing["currency"], existing["timestamp"])

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
    _recalculate_next_snapshot(conn, existing["entity_id"], existing["currency"], existing["timestamp"])
    conn.commit()
