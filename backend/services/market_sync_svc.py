"""Bulk price sync against the external Market API.

Shared by the ``POST /market/sync-prices`` route, the frontend's manual button,
the auto-sync on the market-assets page, and the scheduler cron job. Provides:

- **Single-flight**: only one sync runs at a time (non-blocking guard).
- **Freshness skip**: incremental syncs skip symbols fetched recently.
- **Pacing**: a fixed sleep between symbol requests to avoid provider 500s.
- **last_synced_at** bookkeeping: updated only on successful fetch.
"""

import threading
import time
from datetime import UTC, datetime, timedelta

from db import queries
from db.connection import get_db
from services.api_client import (
    MarketAPIError,
    MarketAPINotFound,
    MarketAPIUnavailable,
    get_market_client,
)
from services.api_resilience import get_breaker

_sync_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _target_codes(conn, full: bool, max_age_hours: float) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT pa.market_code, ma.last_synced_at
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE pa.is_active = 1 AND pa.tracking_mode != 'manual'
        """
    ).fetchall()

    codes: list[str] = []
    cutoff = None if full else datetime.now(UTC) - timedelta(hours=max_age_hours)
    for r in rows:
        code = r["market_code"]
        last = r["last_synced_at"]
        if cutoff is not None and last is not None:
            last_dt = _parse_ts(last)
            if last_dt is not None and last_dt > cutoff:
                continue
        codes.append(code)
    return codes


def sync_prices(full: bool = False, pace: float = 2.0, max_age_hours: float = 1.0) -> dict:
    """Fetch prices for auto-tracked symbols and store into ``prices``.

    Returns a dict with ``synced`` and ``results``, plus optional
    ``busy``/``circuit_open``/``skipped`` markers for the caller.
    """
    if not _sync_lock.acquire(blocking=False):
        return {"synced": 0, "results": [], "busy": True}

    try:
        conn = get_db()
        codes = _target_codes(conn, full, max_age_hours)

        if not codes:
            return {"synced": 0, "results": []}

        client = get_market_client()
        if not get_breaker(client.base_url).can_proceed():
            return {
                "synced": 0,
                "results": [],
                "circuit_open": True,
                "skipped": [{"market_code": c} for c in codes],
            }

        results = []
        synced = 0
        from datetime import date as _date

        for i, market_code in enumerate(codes):
            if i > 0 and pace > 0:
                time.sleep(pace)

            try:
                data = client.get_all(market_code)
            except (MarketAPIUnavailable, MarketAPINotFound, MarketAPIError) as e:
                results.append({"market_code": market_code, "price": None, "error": str(e)})
                continue

            conn.execute(
                "UPDATE market_assets SET last_synced_at = ? WHERE market_code = ?",
                (_now_iso(), market_code),
            )

            current_price = data.get("price")
            if current_price is not None:
                try:
                    today = _date.today().isoformat()
                    queries.create_price(
                        conn,
                        market_code=market_code,
                        timestamp=today,
                        price=float(current_price),
                        provider="market-api",
                    )
                    synced += 1
                    results.append({"market_code": market_code, "price": current_price})
                except Exception:
                    results.append({"market_code": market_code, "price": None, "error": "duplicate"})

            history = data.get("history", {})
            for date_str, ohlcv in sorted(history.items()):
                close = ohlcv.get("Close")
                if close is None:
                    continue
                try:
                    queries.create_price(
                        conn,
                        market_code=market_code,
                        timestamp=date_str,
                        price=float(close),
                        provider="market-api",
                    )
                    synced += 1
                except Exception:
                    continue

        conn.commit()
        return {"synced": synced, "results": results}
    finally:
        _sync_lock.release()
