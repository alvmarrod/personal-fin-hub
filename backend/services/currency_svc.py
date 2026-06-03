from datetime import datetime, timezone
from typing import Optional

from db.connection import get_db
from db import queries
from models import (
    CurrencyPair,
    CurrencyRateResponse,
)


class CurrencyError(Exception):
    pass


class ReversePairExists(CurrencyError):
    pass


class PairNotFound(CurrencyError):
    pass


class RateNotFound(CurrencyError):
    pass


def register_code(code: str) -> CurrencyRateResponse:
    conn = get_db()
    if queries.code_exists(conn, code):
        raise CurrencyError(f"Currency code '{code}' already exists")
    ts = datetime.now(timezone.utc)
    queries.create_self_rate(conn, code, ts)
    conn.commit()
    return CurrencyRateResponse(code=code, base_code=code, rate=1.0, timestamp=ts)


def get_codes() -> list[str]:
    conn = get_db()
    return queries.get_distinct_codes(conn)


def get_pairs(code: Optional[str] = None) -> list[CurrencyPair]:
    conn = get_db()
    pairs = queries.get_distinct_pairs(conn, code)
    return [CurrencyPair(code=p[0], base_code=p[1]) for p in pairs]


def _resolve_direction(
    conn, code: str, base_code: str
) -> tuple[str, str, bool]:
    if queries.pair_exists(conn, code, base_code):
        return code, base_code, False
    if queries.pair_exists(conn, base_code, code):
        return base_code, code, True
    raise PairNotFound(f"Pair ({code}, {base_code}) not found")


def create_rate(
    code: str, base_code: str, rate: float, timestamp: datetime
) -> CurrencyRateResponse:
    conn = get_db()
    if queries.pair_exists(conn, base_code, code):
        raise ReversePairExists(
            f"Reverse pair ({base_code}, {code}) already exists. "
            f"Use that direction or delete it first."
        )
    queries.insert_rate(conn, code, base_code, rate, timestamp)
    conn.commit()
    return CurrencyRateResponse(code=code, base_code=base_code, rate=rate, timestamp=timestamp)


def get_rate(
    code: str, base_code: str, at: Optional[datetime] = None
) -> CurrencyRateResponse:
    conn = get_db()
    stored_code, stored_base_code, invert = _resolve_direction(conn, code, base_code)
    if at:
        row = queries.get_rate_at(conn, stored_code, stored_base_code, at)
    else:
        row = queries.get_latest_rate(conn, stored_code, stored_base_code)
    if row is None:
        raise PairNotFound(f"No rate data for ({code}, {base_code})")
    rate = row["rate"]
    if invert:
        rate = 1.0 / rate
    return CurrencyRateResponse(
        code=code,
        base_code=base_code,
        rate=rate,
        timestamp=row["timestamp"],
        inverted=invert,
    )


def get_history(code: str, base_code: str) -> list[CurrencyRateResponse]:
    conn = get_db()
    stored_code, stored_base_code, invert = _resolve_direction(conn, code, base_code)
    rows = queries.get_rate_history(conn, stored_code, stored_base_code)
    if not rows:
        raise PairNotFound(f"No rate data for ({code}, {base_code})")
    result = []
    for row in rows:
        rate = row["rate"]
        if invert:
            rate = 1.0 / rate
        result.append(
            CurrencyRateResponse(
                code=code,
                base_code=base_code,
                rate=rate,
                timestamp=row["timestamp"],
                inverted=invert,
            )
        )
    return result


def update_rates(
    code: str, base_code: str, timestamps: list[datetime], rates: list[float]
) -> list[CurrencyRateResponse]:
    conn = get_db()
    stored_code, stored_base_code, invert = _resolve_direction(conn, code, base_code)
    if invert:
        raise ReversePairExists(
            f"Pair ({code}, {base_code}) is stored in reverse direction "
            f"({stored_code}, {stored_base_code}). "
            f"Use PUT on that direction instead."
        )
    updated = []
    for ts, r in zip(timestamps, rates):
        ok = queries.update_rate(conn, stored_code, stored_base_code, ts, r)
        if not ok:
            conn.rollback()
            raise RateNotFound(
                f"No rate entry for ({stored_code}, {stored_base_code}) at {ts}"
            )
        updated.append(
            CurrencyRateResponse(
                code=code,
                base_code=base_code,
                rate=r,
                timestamp=ts,
            )
        )
    conn.commit()
    return updated


def delete_pair(code: str, base_code: str) -> bool:
    conn = get_db()
    stored_code, stored_base_code, _ = _resolve_direction(conn, code, base_code)
    deleted = queries.delete_pair(conn, stored_code, stored_base_code)
    conn.commit()
    return deleted
