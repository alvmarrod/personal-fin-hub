"""Investment strategy: effective-dated target sets and current drift.

The five policy buckets and the asset-class mapping live here, in one place.
Targets are stored per bucket, so a future custom-bucket feature can add a
mapping table without migrating target values.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db import queries
from db.connection import get_db
from models import (
    StrategyBucket,
    StrategyDrift,
    StrategyDriftBucket,
    StrategyDriftResidual,
    StrategyHistory,
    StrategyHistoryPoint,
    StrategySetBody,
    StrategyTargetSet,
)
from services import analytics_svc

BUCKETS = tuple(bucket.value for bucket in StrategyBucket)

# Fixed mapping. Subtypes of fixed income collapse into bonds; the two
# judgment calls are documented in doc/plans/investment_strategy.md.
BUCKET_OF_CLASS = {
    "VI": "equities",
    "FI": "bonds",
    "corp FI": "bonds",
    "Sovereign FI": "bonds",
    "mix FI": "bonds",
    "CASH": "cash",
    "Monetary": "cash",
    "REIT": "real_estate",
    "Gold": "gold",
}


class StrategyError(Exception):
    pass


class StrategyNotFound(StrategyError):
    pass


class StrategyExists(StrategyError):
    pass


def _to_set(effective_from: date, targets: dict[str, float], updated_at: str | None = None) -> StrategyTargetSet:
    return StrategyTargetSet(
        effective_from=effective_from,
        targets={bucket: float(targets.get(bucket, 0.0)) for bucket in BUCKETS},
        updated_at=updated_at,
    )


def _group(rows: list[dict]) -> list[StrategyTargetSet]:
    grouped: dict[str, dict] = {}
    for row in rows:
        entry = grouped.setdefault(
            row["effective_from"],
            {"targets": {}, "updated_at": row["updated_at"]},
        )
        entry["targets"][row["bucket"]] = row["target_pct"]
    return [
        _to_set(date.fromisoformat(key), entry["targets"], entry["updated_at"])
        for key, entry in sorted(grouped.items())
    ]


def list_sets() -> list[StrategyTargetSet]:
    conn = get_db()
    try:
        return _group(queries.list_strategy_sets(conn))
    finally:
        conn.close()


def _write(effective_from: date, body: StrategySetBody) -> StrategyTargetSet:
    conn = get_db()
    try:
        iso = effective_from.isoformat()
        queries.delete_strategy_set(conn, iso)
        for bucket in BUCKETS:
            queries.insert_strategy_target(conn, iso, bucket, float(body.targets[bucket]))
        conn.commit()
    finally:
        conn.close()
    return _to_set(effective_from, dict(body.targets))


def create(body: StrategySetBody) -> StrategyTargetSet:
    conn = get_db()
    try:
        if queries.strategy_set_exists(conn, body.effective_from.isoformat()):
            raise StrategyExists("A target set already starts on that date")
    finally:
        conn.close()
    return _write(body.effective_from, body)


def replace(effective_from: date, body: StrategySetBody) -> StrategyTargetSet:
    conn = get_db()
    try:
        if not queries.strategy_set_exists(conn, effective_from.isoformat()):
            raise StrategyNotFound("Target set not found")
    finally:
        conn.close()
    return _write(effective_from, body)


def delete(effective_from: date) -> None:
    conn = get_db()
    try:
        deleted = queries.delete_strategy_set(conn, effective_from.isoformat())
        conn.commit()
    finally:
        conn.close()
    if not deleted:
        raise StrategyNotFound("Target set not found")


def _share(value: float, total: float) -> float:
    return round(value / total * 100 if total else 0.0, 4)


def _resolve(sets: list[StrategyTargetSet], as_of: date) -> StrategyTargetSet | None:
    current = None
    for candidate in sets:
        if candidate.effective_from <= as_of:
            current = candidate
    return current


def _today() -> date:
    """Today in the profile timezone, with a server-local fallback."""
    conn = get_db()
    try:
        name = queries.get_profile_timezone(conn)
    finally:
        conn.close()
    if name:
        try:
            return datetime.now(ZoneInfo(name)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return date.today()


def drift(display_currency: str | None = None, today: date | None = None) -> StrategyDrift:
    as_of = today or _today()
    current = _resolve(list_sets(), as_of)

    if current is None:
        return StrategyDrift(
            effective_from=None,
            as_of=as_of,
            total=0.0,
            rate_missing=False,
            buckets=[],
            unassigned=StrategyDriftResidual(value=0.0, share_pct=0.0),
        )

    values = dict.fromkeys(BUCKETS, 0.0)
    missing = dict.fromkeys(BUCKETS, False)
    unassigned_value = 0.0
    unassigned_missing = False

    for line in analytics_svc.get_holdings_by_entity(display_currency):
        bucket = BUCKET_OF_CLASS.get(line.asset_class or "")
        if bucket is None:
            unassigned_value += line.current_value
            unassigned_missing = unassigned_missing or line.rate_missing
        else:
            values[bucket] += line.current_value
            missing[bucket] = missing[bucket] or line.rate_missing

    total = sum(values.values()) + unassigned_value

    def share(value: float) -> float:
        return value / total * 100 if total else 0.0

    buckets = [
        StrategyDriftBucket(
            bucket=bucket,
            target_pct=current.targets.get(bucket, 0.0),
            value=round(values[bucket], 4),
            share_pct=round(share(values[bucket]), 4),
            drift_pp=round(share(values[bucket]) - current.targets.get(bucket, 0.0), 4),
            amount_to_move=round(current.targets.get(bucket, 0.0) / 100 * total - values[bucket], 4),
            rate_missing=missing[bucket],
        )
        for bucket in BUCKETS
    ]

    return StrategyDrift(
        effective_from=current.effective_from,
        as_of=as_of,
        total=round(total, 4),
        rate_missing=any(missing.values()) or unassigned_missing,
        buckets=buckets,
        unassigned=StrategyDriftResidual(
            value=round(unassigned_value, 4),
            share_pct=round(share(unassigned_value), 4),
            rate_missing=unassigned_missing,
        ),
    )


def history(
    start_date: str,
    end_date: str,
    interval: str = "month",
    display_currency: str | None = None,
) -> StrategyHistory:
    rows = analytics_svc.get_historical_values_by_asset_class(start_date, end_date, interval, None, display_currency)
    sets = list_sets()

    by_date: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = BUCKET_OF_CLASS.get(row.asset_class or "") or "unassigned"
        values = by_date.setdefault(row.date, {})
        values[bucket] = values.get(bucket, 0.0) + row.value

    points: list[StrategyHistoryPoint] = []
    for date_str in sorted(by_date):
        values = by_date[date_str]
        total = sum(values.values())
        target = _resolve(sets, date.fromisoformat(date_str))

        for bucket in BUCKETS:
            value = values.get(bucket, 0.0)
            points.append(
                StrategyHistoryPoint(
                    date=date_str,
                    bucket=bucket,
                    value=round(value, 4),
                    share_pct=_share(value, total),
                    target_pct=target.targets.get(bucket) if target else None,
                )
            )

        unassigned = values.get("unassigned", 0.0)
        if unassigned:
            points.append(
                StrategyHistoryPoint(
                    date=date_str,
                    bucket="unassigned",
                    value=round(unassigned, 4),
                    share_pct=_share(unassigned, total),
                    target_pct=None,
                )
            )

    return StrategyHistory(points=points)
