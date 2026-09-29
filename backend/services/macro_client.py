"""Provider clients for the macro data source layer (Phase 1).

Two providers, per ``doc/datasources/macro.md``:

- **Investing.com economic calendar** — HTML page with the full release history
  embedded as a ``__NEXT_DATA__`` JSON island. No browser is needed: the data is
  server-rendered inside that JSON. Only the first page is read (100 releases);
  the "Show More" pagination is not implemented (accepted limitation, Phase 1).
- **ECB Data Portal** — a data-detail JSON endpoint that returns the full
  observation history as a JSON array, no pagination.

Both clients return a flat list of ``Observation(obs_date, value)`` in the units
the provider reports. Normalization to a world KPI is out of scope (Phase 2,
``doc/kpis/world_calc.md``).
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from services.api_resilience import get_breaker, should_retry_http, sleep_between_attempts
from services.config import config

logger = logging.getLogger(__name__)

# The provider's release value is often a percentage string like "1.00%" or
# "-0.10%"; a bare number is also accepted. A non-numeric placeholder ("-",
# "--") means "no value yet".
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


class MacroClientError(Exception):
    """Base exception for macro provider errors."""


class MacroUnavailable(MacroClientError):
    """Raised when a provider is unreachable or the circuit is open."""


class MacroParseError(MacroClientError):
    """Raised when a provider response cannot be parsed."""


@dataclass(frozen=True)
class Observation:
    """One release of a macro series: the observation date and its value."""

    obs_date: date
    value: float


def _parse_number(raw: object) -> float | None:
    """Parse a provider value into a float, or None when there is no value.

    Accepts numbers and strings such as ``"1.00%"`` / ``"-0.10%"`` / ``"3.2"``.
    A placeholder with no digits ("-", "--", "", None) yields None.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    match = _NUMBER_RE.search(str(raw))
    return float(match.group()) if match else None


def _parse_date(raw: object) -> date | None:
    """Parse a provider timestamp/period into a calendar date."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        # Handles "2026-09-17T09:00:00Z" and "2026-09-17".
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    # ECB PERSIST: PERIOD may be "2026-09" (monthly) or "2026".
    match = re.match(r"(\d{4})-(\d{2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    match = re.match(r"(\d{4})$", text)
    if match:
        return date(int(match.group(1)), 1, 1)
    return None


def parse_investing_html(html: str) -> list[Observation]:
    """Extract releases from an Investing.com calendar page's HTML.

    The releases are embedded in the ``__NEXT_DATA__`` JSON island at
    ``props.pageProps.state.economicCalendarEventStore.occurrences``. Releases
    without a reported ``actual`` (not yet published) are skipped.
    """
    match = _NEXT_DATA_RE.search(html)
    if match is None:
        raise MacroParseError("Investing.com page has no __NEXT_DATA__ island")
    try:
        payload = json.loads(match.group(1))
        occurrences = payload["props"]["pageProps"]["state"]["economicCalendarEventStore"]["occurrences"]
    except (ValueError, KeyError, TypeError) as e:
        raise MacroParseError(f"Investing.com __NEXT_DATA__ shape unexpected: {e}") from e

    observations: list[Observation] = []
    for occurrence in occurrences:
        obs_date = _parse_date(occurrence.get("occurrence_time"))
        value = _parse_number(occurrence.get("actual"))
        if obs_date is None or value is None:
            continue
        observations.append(Observation(obs_date=obs_date, value=value))
    return observations


def parse_ecb_json(payload: object) -> list[Observation]:
    """Extract releases from an ECB Data Portal data-detail JSON response.

    The endpoint returns a JSON array (or an object wrapping one under
    ``dataSets``/``data``); each element carries ``PERIOD`` and the reported
    value. ``OBS_VALUE_AS_IS`` is preferred over the rounded ``OBS`` when present.
    """
    rows = payload
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("dataSets") or payload.get("observations") or []
    if not isinstance(rows, list):
        raise MacroParseError("ECB response is not a JSON array")

    observations: list[Observation] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        obs_date = _parse_date(row.get("PERIOD") or row.get("period"))
        value = _parse_number(row.get("OBS_VALUE_AS_IS") if row.get("OBS_VALUE_AS_IS") is not None else row.get("OBS"))
        if obs_date is None or value is None:
            continue
        observations.append(Observation(obs_date=obs_date, value=value))
    return observations


class _BaseClient:
    """Shared HTTP + resilience plumbing for macro providers."""

    def __init__(self, base_url: str, timeout: int | None = None):
        self.base_url = base_url
        self.timeout = timeout or config.macro_timeout
        self._client = httpx.Client(base_url=base_url, timeout=self.timeout, follow_redirects=True)

    def _get(self, path: str) -> httpx.Response:
        breaker = get_breaker(self.base_url)
        if not breaker.allow_request():
            raise MacroUnavailable(f"macro provider {self.base_url} unavailable (circuit open)")

        attempts = max(1, config.market_api_retry_attempts)
        for attempt in range(1, attempts + 1):
            try:
                response = self._client.get(path)
                response.raise_for_status()
                breaker.record_success()
                return response
            except httpx.TransportError as e:
                if attempt < attempts:
                    sleep_between_attempts(
                        attempt,
                        config.market_api_retry_base_delay,
                        config.market_api_retry_max_delay,
                    )
                    continue
                breaker.record_failure()
                raise MacroUnavailable(f"cannot reach {self.base_url}: {type(e).__name__}") from None
            except httpx.HTTPStatusError as e:
                if should_retry_http(e.response.status_code) and attempt < attempts:
                    sleep_between_attempts(
                        attempt,
                        config.market_api_retry_base_delay,
                        config.market_api_retry_max_delay,
                        e.response,
                    )
                    continue
                if should_retry_http(e.response.status_code):
                    breaker.record_failure()
                raise MacroClientError(f"macro provider error {e.response.status_code} for {path}") from e

        raise MacroUnavailable(f"cannot reach {self.base_url}")  # pragma: no cover - attempts >= 1

    def close(self) -> None:
        self._client.close()


class InvestingClient(_BaseClient):
    """Fetches and parses Investing.com economic-calendar pages."""

    BASE_URL = "https://www.investing.com"

    # Investing.com returns HTTP 403 to clients without a browser-like
    # User-Agent, so a realistic UA (and Accept-Language) is required.
    _BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)
        self._client.headers.update(self._BROWSER_HEADERS)

    def fetch(self, url: str) -> list[Observation]:
        """Fetch one calendar page (URL) and return its releases."""
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        return parse_investing_html(response.text)


class ECBClient(_BaseClient):
    """Fetches and parses the ECB Data Portal data-detail JSON endpoint."""

    BASE_URL = "https://data.ecb.europa.eu"

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        """Fetch one series (URL) and return its full observation history."""
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        try:
            payload = response.json()
        except ValueError as e:
            raise MacroParseError(f"ECB response is not JSON: {e}") from e
        return parse_ecb_json(payload)


def fetch_series(provider: str, url: str) -> list[Observation]:
    """Dispatch to the right client for a provider tag ("investing-com" | "ecb")."""
    client: InvestingClient | ECBClient
    if provider == "ecb":
        client = ECBClient()
    elif provider == "investing-com":
        client = InvestingClient()
    else:
        raise MacroClientError(f"unknown macro provider: {provider}")
    try:
        return client.fetch(url)
    finally:
        client.close()
