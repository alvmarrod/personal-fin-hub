import time
from datetime import UTC, date, datetime, timedelta

from db import queries
from db.analytics_queries import (
    get_investment_by_currency_as_of,
    get_total_cash_by_currency_as_of,
)
from db.connection import get_db
from models import (
    CurrencyHoldingHistory,
    CurrencyHoldingSeries,
    CurrencyPair,
    CurrencyRateResponse,
    RateChartDataset,
    RateChartResponse,
)
from services.api_client import get_market_client
from services.api_resilience import get_breaker


class CurrencyError(Exception):
    pass


class CurrencyCodeHasDependents(CurrencyError):
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
    ts = datetime.now(UTC)
    queries.create_self_rate(conn, code, ts)
    conn.commit()
    return CurrencyRateResponse(code=code, base_code=code, rate=1.0, timestamp=ts)


def get_codes() -> list[str]:
    conn = get_db()
    return queries.get_distinct_codes(conn)


def get_pairs(code: str | None = None) -> list[CurrencyPair]:
    conn = get_db()
    pairs = queries.get_distinct_pairs(conn, code)
    return [CurrencyPair(code=p[0], base_code=p[1]) for p in pairs]


def _resolve_direction(conn, code: str, base_code: str) -> tuple[str, str, bool]:
    if queries.pair_exists(conn, code, base_code):
        return code, base_code, False
    if queries.pair_exists(conn, base_code, code):
        return base_code, code, True
    raise PairNotFound(f"Pair ({code}, {base_code}) not found")


def create_rate(code: str, base_code: str, rate: float, timestamp: datetime) -> CurrencyRateResponse:
    conn = get_db()
    if queries.pair_exists(conn, base_code, code):
        raise ReversePairExists(
            f"Reverse pair ({base_code}, {code}) already exists. Use that direction or delete it first."
        )
    queries.insert_rate(conn, code, base_code, rate, timestamp)
    conn.commit()
    return CurrencyRateResponse(code=code, base_code=base_code, rate=rate, timestamp=timestamp)


def get_rate(code: str, base_code: str, at: datetime | None = None) -> CurrencyRateResponse:
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
    if queries.pair_exists(conn, base_code, code):
        raise ReversePairExists(
            f"Reverse pair ({base_code}, {code}) already exists. Use that direction or delete it first."
        )
    updated = []
    for ts, r in zip(timestamps, rates, strict=False):
        queries.upsert_rate(conn, code, base_code, r, ts)
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


def delete_code(code: str) -> None:
    conn = get_db()
    if not queries.code_exists(conn, code):
        raise CurrencyError(f"Currency code '{code}' not found")
    if queries.currency_code_has_dependents(conn, code):
        raise CurrencyCodeHasDependents(
            f"Currency code '{code}' has market assets, transactions, fees, taxes, or snapshots referencing it"
        )
    queries.delete_code(conn, code)
    conn.commit()


def _get_fx_pairs(codes: list[str]) -> list[tuple[str, str, str]]:
    pairs = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            pairs.append((a, b, f"{a}{b}=X"))
    return pairs


# The Market API serves at most 1 year of history per request, so deep syncs
# are chunked into consecutive windows that never exceed this span.
_MAX_WINDOW_DAYS = 365

# Staleness rule (§16.4): FX rates are previous closes, so a gap of less than
# two business days between the rate date and the reference date is the
# routine weekend / latest-close case and is never reported. Weekends do not
# count toward the gap; there is no holiday calendar (documented limitation).
_STALE_BUSINESS_DAYS = 2


def business_days_between(start: date, end: date) -> int:
    """Count business days (Mon-Fri) after ``start`` up to ``end`` inclusive.

    ``end`` before or equal to ``start`` yields 0, so forward resolutions and
    same-day rates are never stale by construction.
    """
    if end <= start:
        return 0
    days = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


def is_stale_rate(rate_date: date, reference_date: date) -> bool:
    """True when the rate is at least ``_STALE_BUSINESS_DAYS`` old."""
    return business_days_between(rate_date, reference_date) >= _STALE_BUSINESS_DAYS


def _sync_windows(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Split ``[start, end]`` into inclusive date windows of <= 1 year."""
    windows: list[tuple[datetime, datetime]] = []
    current = start
    while current < end:
        window_end = min(current + timedelta(days=_MAX_WINDOW_DAYS), end)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def sync_rates(pace_seconds: float = 0.5) -> dict:
    conn = get_db()
    codes = queries.get_distinct_codes(conn)
    if not codes:
        raise CurrencyError("No currency codes to sync")

    fx_pairs = _get_fx_pairs(codes)
    client = get_market_client()
    if get_breaker(client.base_url).is_open():
        return {
            "synced": True,
            "pairs": [],
            "total_rates": 0,
            "circuit_open": True,
            "skipped": [{"code": code, "base_code": base_code} for code, base_code, _ in fx_pairs],
        }

    # Deep backfill: from the earliest transaction (minus a small buffer) to
    # today, so historical conversions never rely on closest-in-time guesses
    # when the Market API can serve the exact dates. Falls back to the
    # provider's default recent window when there is no transaction history.
    end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    earliest_raw = queries.get_earliest_transaction_timestamp(conn)
    if earliest_raw:
        try:
            iso = earliest_raw[:-1] + "+00:00" if earliest_raw.endswith("Z") else earliest_raw
            start = datetime.fromisoformat(iso).replace(tzinfo=None) - timedelta(days=7)
        except ValueError:
            start = None
    else:
        start = None

    windows = _sync_windows(start, end) if start else [(start, end)]

    def _fetch(symbol: str) -> list[dict]:
        """Fetch history per window; returns raw history dicts."""
        histories: list[dict] = []
        for w_start, w_end in windows:
            if pace_seconds > 0 and histories:
                time.sleep(pace_seconds)
            if w_start is None:
                data = client.get_all(symbol)
            else:
                data = client.get_all(
                    symbol,
                    start=w_start.strftime("%Y-%m-%d"),
                    end=w_end.strftime("%Y-%m-%d"),
                )
            histories.append(data.get("history", {}))
        return histories

    pairs_result = []
    total = 0
    any_error = None

    for code, base_code, symbol in fx_pairs:
        try:
            histories = _fetch(symbol)
        except Exception as e:
            any_error = f"Market API error for {symbol}: {e}"
            pairs_result.append({"code": code, "base_code": base_code, "rates_added": 0, "error": str(e)})
            continue

        count = 0
        for history in histories:
            for date_str, ohlcv in history.items():
                close = ohlcv.get("Close")
                if close is None:
                    continue
                ts = datetime.fromisoformat(date_str).replace(tzinfo=None)
                try:
                    queries.upsert_rate(conn, code, base_code, close, ts)
                    count += 1
                except Exception:
                    continue
        conn.commit()
        total += count
        pair_info = {"code": code, "base_code": base_code, "rates_added": count}
        if start:
            pair_info["windows"] = len(windows)
            pair_info["start"] = start.strftime("%Y-%m-%d")
            pair_info["end"] = end.strftime("%Y-%m-%d")
        pairs_result.append(pair_info)

    result = {"synced": True, "pairs": pairs_result, "total_rates": total}
    if any_error:
        result["warning"] = any_error
    return result


def _generate_dates(start_date: str, end_date: str) -> list[str]:
    from datetime import timedelta

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def get_historical_holdings(
    start_date: str,
    end_date: str,
    display_currency: str = "USD",
) -> CurrencyHoldingHistory:
    conn = get_db()
    dates = _generate_dates(start_date, end_date)
    if not dates:
        return CurrencyHoldingHistory(dates=[], series=[], latest_raw={})

    codes = queries.get_distinct_codes(conn)
    if not codes:
        return CurrencyHoldingHistory(dates=dates, series=[], latest_raw={})

    rate_index: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for c in codes:
        if c == display_currency:
            continue
        try:
            history = get_history(c, display_currency)
            rate_index[(c, display_currency)] = [(h.timestamp.strftime("%Y-%m-%d"), h.rate) for h in history]
        except PairNotFound:
            pass

    from bisect import bisect_right
    from collections import defaultdict

    all_currencies: set[str] = set()
    daily_raw: list[dict[str, float]] = []

    for dt in dates:
        cash = get_total_cash_by_currency_as_of(conn, dt)
        inv = get_investment_by_currency_as_of(conn, dt)

        raw: dict[str, float] = defaultdict(float)
        for curr, val in cash.items():
            raw[curr] += val
            all_currencies.add(curr)
        for curr, val in inv.items():
            raw[curr] += val
            all_currencies.add(curr)

        daily_raw.append(dict(raw))

    series_map: dict[str, list[float]] = {c: [] for c in all_currencies}

    for i, dt in enumerate(dates):
        raw = daily_raw[i]
        for curr in all_currencies:
            total = raw.get(curr, 0.0)
            if curr == display_currency:
                series_map[curr].append(total)
            else:
                entries = rate_index.get((curr, display_currency), [])
                if entries:
                    ts_list = [e[0] for e in entries]
                    idx = bisect_right(ts_list, dt) - 1
                    if idx >= 0:
                        rate = entries[idx][1]
                        series_map[curr].append(total * rate)
                    else:
                        series_map[curr].append(total)
                else:
                    series_map[curr].append(total)

    series = [CurrencyHoldingSeries(currency=c, values=series_map[c]) for c in sorted(all_currencies)]

    latest_raw = daily_raw[-1] if daily_raw else {}

    return CurrencyHoldingHistory(
        dates=dates,
        series=series,
        latest_raw=latest_raw,
    )


def get_rate_chart_data(
    base_currency: str = "USD",
    start_date: str | None = None,
    end_date: str | None = None,
) -> RateChartResponse:
    codes = get_codes()
    other_codes = [c for c in codes if c != base_currency]
    if not other_codes:
        return RateChartResponse(labels=[], datasets=[])

    default_colors = [
        "#4263eb",
        "#2f9e44",
        "#f08c00",
        "#e03131",
        "#845ef7",
        "#20c997",
        "#ff6b6b",
        "#339af0",
    ]

    labels: list[str] = []
    datasets: list[RateChartDataset] = []

    for idx, code in enumerate(other_codes):
        try:
            history = get_history(code, base_currency)
        except PairNotFound:
            continue

        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            history = [h for h in history if h.timestamp >= start_dt]
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            history = [h for h in history if h.timestamp <= end_dt]

        if not history:
            continue

        history.sort(key=lambda h: h.timestamp)

        if not labels:
            labels = [h.timestamp.strftime("%Y-%m-%d") for h in history]

        raw_data = [h.rate for h in history]

        if code == "JPY":
            label = f"JPY/{base_currency}"
            data = [1.0 / d if d != 0 else 0 for d in raw_data]
            axis = "right"
        elif base_currency == "JPY":
            label = f"JPY/{code}"
            data = raw_data
            axis = "right"
        else:
            label = f"{code}/{base_currency}"
            data = raw_data
            axis = "left"

        datasets.append(
            RateChartDataset(
                label=label,
                data=data,
                axis=axis,
                color=default_colors[idx % len(default_colors)],
            )
        )

    return RateChartResponse(labels=labels, datasets=datasets)
