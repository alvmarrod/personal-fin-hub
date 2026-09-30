"""Macro series sync (Phase 1 — raw data source layer).

Fetches each Wired macro series from its provider and stores the raw
``(obs_date, value)`` points into ``macro_series_observations``. No KPI
normalization happens here — that is Phase 2 (``doc/kpis/``).

Shared by the scheduler cron job (twice daily, ``macro.sync_hours_utc``) and the
manual CLI (``scripts/macro_sync.py``). Mirrors ``market_sync_svc``:
single-flight, a freshness skip, pacing between requests, and a per-series
result shape. A provider outage keeps the last known data (upsert is additive).
"""

import threading
import time
from datetime import UTC, datetime, timedelta

from db import queries
from db.connection import get_db
from services.api_resilience import get_breaker
from services.config import config
from services.macro_client import (
    BlsClient,
    BojClient,
    ECBClient,
    ECBDataClient,
    EurostatClient,
    FredClient,
    MacroClientError,
    MacroUnavailable,
    fetch_series,
)

_sync_lock = threading.Lock()

# Providers whose breaker we consult for the fail-fast pre-check.
_PROVIDER_BASE_URLS = [
    ECBClient.BASE_URL,
    ECBDataClient.BASE_URL,
    BojClient.BASE_URL,
    BlsClient.BASE_URL,
    FredClient.BASE_URL,
    EurostatClient.BASE_URL,
    config.market_api_base_url,
]


def _now() -> datetime:
    return datetime.now(UTC)


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


def _is_fresh(series: dict, now: datetime, max_age_hours: float) -> bool:
    last = _parse_ts(series.get("last_synced_at"))
    return last is not None and (now - last) < timedelta(hours=max_age_hours)


def sync_series(slugs: list[str] | None = None) -> dict:
    """Sync all (or the named) macro series.

    Returns ``{"synced": bool, "series": [{slug, added, error?}], "busy"?,
    "circuit_open"?}``. ``added`` counts newly inserted observations; a series
    that fails records its error and leaves existing data untouched.
    """
    if not _sync_lock.acquire(blocking=False):
        return {"synced": False, "series": [], "busy": True}

    try:
        conn = get_db()
        all_series = queries.get_all_macro_series(conn)
        if slugs is not None:
            wanted = set(slugs)
            all_series = [s for s in all_series if s["slug"] in wanted]

        if not all_series:
            return {"synced": True, "series": []}

        circuit_open = all(not get_breaker(url).can_proceed() for url in _PROVIDER_BASE_URLS)

        now = _now()
        freshness = config.macro_sync_freshness_hours
        pace = config.macro_sync_pace_seconds
        results: list[dict] = []
        total_added = 0

        for i, series in enumerate(all_series):
            slug = series["slug"]
            if not series.get("provider") or not series.get("source_url"):
                results.append({"slug": slug, "added": 0, "skipped": "no-source"})
                continue
            if _is_fresh(series, now, freshness):
                results.append({"slug": slug, "added": 0, "skipped": "fresh"})
                continue
            if i > 0 and pace > 0:
                time.sleep(pace)

            try:
                observations = fetch_series(series["provider"], series["source_url"])
            except (MacroUnavailable, MacroClientError) as e:
                results.append({"slug": slug, "added": 0, "error": str(e)})
                continue

            added = 0
            for obs in observations:
                if queries.upsert_macro_observation(conn, slug, obs.obs_date.isoformat(), obs.value):
                    added += 1
            queries.touch_macro_series_synced(conn, slug, now.isoformat())
            conn.commit()

            total_added += added
            results.append({"slug": slug, "added": added})

        result: dict = {"synced": True, "series": results, "total_added": total_added}
        if circuit_open:
            result["circuit_open"] = True
        return result
    finally:
        _sync_lock.release()
