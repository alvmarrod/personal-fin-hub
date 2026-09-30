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
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

from services.api_client import (
    MarketAPIError,
    MarketAPINotFound,
    MarketAPIUnavailable,
    get_market_client,
)
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


def parse_ecb_sdmx_json(payload: object, change_points_only: bool = False) -> list[Observation]:
    """Extract observations from an ECB data-api SDMX-JSON response.

    The ``data-api.ecb.europa.eu/service/data`` endpoint returns SDMX-JSON:
    ``dataSets[].series[].observations`` keyed by the index of the ``TIME_PERIOD``
    observation dimension. Each observation's first element is the value.

    ``change_points_only`` keeps only the observations where the value differs
    from the previous one — used for the "date of changes" deposit-facility
    series, where repeated daily values mean the rate is unchanged, so the
    result is one observation per policy-rate change (the existing semantics).
    """
    if not isinstance(payload, dict):
        raise MacroParseError("ECB SDMX response is not a JSON object")
    try:
        datasets = payload["dataSets"]
        try:
            dims = payload["structure"]["dimensions"]["observation"]
        except (KeyError, TypeError):
            dims = payload["data"]["structure"]["dimensions"]["observation"]
        time_values = next(x for x in dims if x["id"] == "TIME_PERIOD")["values"]
    except (KeyError, TypeError, StopIteration) as e:
        raise MacroParseError(f"ECB SDMX shape unexpected: {e}") from e

    observations: list[Observation] = []
    for dataset in datasets:
        for series in dataset.get("series", {}).values():
            for key, raw in series.get("observations", {}).items():
                index = int(str(key).split(":")[0])
                obs_date = _parse_date(time_values[index]["id"])
                value = _parse_number(raw[0] if isinstance(raw, list) and raw else raw)
                if obs_date is None or value is None:
                    continue
                observations.append(Observation(obs_date=obs_date, value=value))

    observations.sort(key=lambda o: o.obs_date)
    if change_points_only:
        filtered: list[Observation] = []
        previous: float | None = None
        for obs in observations:
            if previous is None or obs.value != previous:
                filtered.append(obs)
                previous = obs.value
        return filtered
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


def change_points_only(observations: list[Observation]) -> list[Observation]:
    """Keep only observations whose value differs from the previous one.

    Used for a "date of changes" policy-rate series: repeated daily values mean
    the rate is unchanged, so the result is one observation per change.
    """
    filtered: list[Observation] = []
    previous: float | None = None
    for obs in sorted(observations, key=lambda o: o.obs_date):
        if previous is None or obs.value != previous:
            filtered.append(obs)
            previous = obs.value
    return filtered


def parse_boj_json(payload: object) -> list[Observation]:
    """Extract observations from a BOJ Time-Series Data Search ``getDataCode``
    response.

    Shape: ``RESULTSET[].VALUES.SURVEY_DATES`` and ``.VALUES`` (parallel arrays).
    Dates are ``YYYYMMDD`` (daily) or ``YYYYMM`` (monthly).
    """
    if not isinstance(payload, dict):
        raise MacroParseError("BOJ response is not a JSON object")
    resultset = payload.get("RESULTSET")
    if not isinstance(resultset, list):
        raise MacroParseError("BOJ response has no RESULTSET")

    observations: list[Observation] = []
    for series in resultset:
        values = series.get("VALUES") or {}
        surveys = values.get("SURVEY_DATES") or []
        points = values.get("VALUES") or []
        for raw_date, raw_value in zip(surveys, points, strict=False):
            obs_date = _parse_boj_date(raw_date)
            value = _parse_number(raw_value)
            if obs_date is None or value is None:
                continue
            observations.append(Observation(obs_date=obs_date, value=value))
    return observations


def _parse_boj_date(raw: object) -> date | None:
    text = str(raw).strip()
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    if len(text) == 6 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), 1)
    return None


def parse_bls_json(payload: object) -> list[Observation]:
    """Extract the monthly index from a BLS Public Data API response.

    Shape: ``Results.series[0].data[]`` with ``year``, ``period`` (``M01``…)
    and ``value``. The index is stored as reported; the world-KPI derivation
    layer applies the YoY normalization.
    """
    if not isinstance(payload, dict):
        raise MacroParseError("BLS response is not a JSON object")
    if payload.get("status") not in (None, "REQUEST_SUCCEEDED"):
        raise MacroParseError(f"BLS request failed: {payload.get('status')} {payload.get('message')}")
    try:
        rows = payload["Results"]["series"][0]["data"]
    except (KeyError, IndexError, TypeError) as e:
        raise MacroParseError(f"BLS response shape unexpected: {e}") from e

    observations: list[Observation] = []
    for row in rows:
        period = str(row.get("period", ""))
        if not period.startswith("M") or period == "M13":
            continue  # skip annual averages / non-monthly rows
        try:
            obs_date = date(int(row["year"]), int(period[1:]), 1)
        except (KeyError, ValueError, TypeError):
            continue
        value = _parse_number(row.get("value"))
        if value is None:
            continue
        observations.append(Observation(obs_date=obs_date, value=value))
    return observations


def parse_fred_csv(text: str) -> list[Observation]:
    """Extract a monthly level series from a FRED ``fredgraph.csv`` response.

    Two columns: ``observation_date`` (YYYY-MM-DD) and the series value; missing
    values are the literal ``.``.
    """
    observations: list[Observation] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("observation_date"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        obs_date = _parse_date(parts[0])
        value = _parse_number(parts[1])
        if obs_date is None or value is None:
            continue
        observations.append(Observation(obs_date=obs_date, value=value))
    return observations


def parse_eurostat_json(payload: object) -> list[Observation]:
    """Extract observations from a Eurostat JSON-stat (``format=JSON``) response.

    ``value`` maps a flat observation index to the value; ``dimension.time.
    category.index`` maps each period label to that index.
    """
    if not isinstance(payload, dict):
        raise MacroParseError("Eurostat response is not a JSON object")
    try:
        values = payload["value"]
        time_index = payload["dimension"]["time"]["category"]["index"]
    except (KeyError, TypeError) as e:
        raise MacroParseError(f"Eurostat shape unexpected: {e}") from e

    index_to_period = {int(idx): label for label, idx in time_index.items()}
    observations: list[Observation] = []
    for key, raw in values.items():
        period = index_to_period.get(int(key))
        obs_date = _parse_date(period) if period else None
        value = _parse_number(raw)
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

    def _post(self, path: str, json_body: dict) -> httpx.Response:
        """POST JSON with the same breaker/retry behavior as ``_get``."""
        breaker = get_breaker(self.base_url)
        if not breaker.allow_request():
            raise MacroUnavailable(f"macro provider {self.base_url} unavailable (circuit open)")

        attempts = max(1, config.market_api_retry_attempts)
        for attempt in range(1, attempts + 1):
            try:
                response = self._client.post(path, json=json_body)
                response.raise_for_status()
                breaker.record_success()
                return response
            except httpx.TransportError:
                if attempt < attempts:
                    sleep_between_attempts(
                        attempt,
                        config.market_api_retry_base_delay,
                        config.market_api_retry_max_delay,
                    )
                    continue
                breaker.record_failure()
                raise MacroUnavailable(f"cannot reach {self.base_url}") from None
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


class ECBDataClient(_BaseClient):
    """Fetches SDMX-JSON series from the ECB data-api service.

    Used for series that live on ``data-api.ecb.europa.eu/service/data`` (SDMX),
    as opposed to the Data Portal data-detail endpoint handled by ``ECBClient``.
    The deposit-facility "date of changes" series repeats a daily value until
    the rate changes, so only change points are returned to preserve the
    existing one-observation-per-policy-change semantics.
    """

    BASE_URL = "https://data-api.ecb.europa.eu"

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        try:
            payload = response.json()
        except ValueError as e:
            raise MacroParseError(f"ECB data-api response is not JSON: {e}") from e
        return parse_ecb_sdmx_json(payload, change_points_only=True)


class BojClient(_BaseClient):
    """Bank of Japan Time-Series Data Search API.

    The endpoint URL in the series row carries the full query
    (``?db=...&code=...``). A daily "date of changes" policy-rate series is
    reduced to change points. Level series (e.g. M2) are returned as reported;
    the world-KPI derivation layer converts them to a growth rate.
    """

    BASE_URL = "https://www.stat-search.boj.or.jp"
    # Daily policy-rate codes: reduce to change points.
    _CHANGE_POINT_CODES = ("MADR1Z", "MADR1M")

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        try:
            payload = response.json()
        except ValueError as e:
            raise MacroParseError(f"BOJ response is not JSON: {e}") from e
        observations = parse_boj_json(payload)
        if any(code in url for code in self._CHANGE_POINT_CODES):
            return change_points_only(observations)
        return observations


class BlsClient(_BaseClient):
    """U.S. Bureau of Labor Statistics Public Data API (v2, keyless).

    Stores the CPI-U index (``CUUR0000SA0``) as reported; the world-KPI
    derivation layer converts it to a YoY growth rate.
    """

    BASE_URL = "https://api.bls.gov"
    SERIES_ID = "CUUR0000SA0"

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        response = self._post(
            "/publicAPI/v2/timeseries/data/",
            # BLS caps an unregistered v2 query at 10 years; take the most
            # recent window so the series stays current.
            {
                "seriesid": [self.SERIES_ID],
                "startyear": str(date.today().year - 9),
                "endyear": str(date.today().year),
            },
        )
        try:
            payload = response.json()
        except ValueError as e:
            raise MacroParseError(f"BLS response is not JSON: {e}") from e
        return parse_bls_json(payload)


class FredClient(_BaseClient):
    """Federal Reserve H.6 series via the FRED CSV graph endpoint (keyless)."""

    BASE_URL = "https://fred.stlouisfed.org"

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        return parse_fred_csv(response.text)


class EurostatClient(_BaseClient):
    """Eurostat dissemination API (JSON-stat); keyless."""

    BASE_URL = "https://ec.europa.eu"

    def __init__(self, timeout: int | None = None):
        super().__init__(self.BASE_URL, timeout)

    def fetch(self, url: str) -> list[Observation]:
        path = url.split(self.BASE_URL, 1)[-1] if url.startswith(self.BASE_URL) else url
        response = self._get(path)
        try:
            payload = response.json()
        except ValueError as e:
            raise MacroParseError(f"Eurostat response is not JSON: {e}") from e
        return parse_eurostat_json(payload)


def _market_history_windows(start: date, end: date, max_days: int) -> list[tuple[date, date]]:
    """Split ``[start, end]`` into inclusive windows of at most ``max_days``."""
    windows: list[tuple[date, date]] = []
    current = start
    while current < end:
        window_end = min(current + timedelta(days=max_days), end)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows or [(start, end)]


class MarketApiMacroClient:
    """A market series served by the External Market API, stored as a macro
    series (the CLOSE value per date).

    The provider serves at most one year of history per request, so the
    lookback window is chunked into consecutive <= 1-year windows. Used for
    ``^IRX`` (13-week T-bill yield) as the ``policy_rate`` USA proxy.
    """

    _MAX_WINDOW_DAYS = 365

    def __init__(self):
        self.base_url = config.market_api_base_url

    def fetch(self, url: str) -> list[Observation]:
        symbol = url
        client = get_market_client()
        today = date.today()
        start = today - timedelta(days=int(config.market_api_policy_rate_history_years) * 365)
        windows = _market_history_windows(start, today, self._MAX_WINDOW_DAYS)
        pace = config.macro_sync_pace_seconds

        observations: list[Observation] = []
        for index, (window_start, window_end) in enumerate(windows):
            if index > 0 and pace > 0:
                time.sleep(pace)
            try:
                data = client.get_all(symbol, start=window_start.isoformat(), end=window_end.isoformat())
            except (MarketAPIUnavailable, MarketAPINotFound, MarketAPIError) as e:
                raise MacroUnavailable(f"market-api {symbol}: {e}") from e
            for date_str, ohlcv in (data.get("history") or {}).items():
                close = ohlcv.get("Close")
                obs_date = _parse_date(date_str)
                if obs_date is None or close is None:
                    continue
                observations.append(Observation(obs_date=obs_date, value=float(close)))
        return observations

    def close(self) -> None:
        """No owned HTTP client — ``get_market_client`` is shared."""


def fetch_series(provider: str, url: str) -> list[Observation]:
    """Dispatch to the right client for a provider tag.

    Providers: ``ecb`` (ECB JSON — Data Portal data-detail or data-api SDMX,
    chosen from the source URL host), ``boj``, ``bls``, ``fred``, ``eurostat``,
    ``market-api`` (a symbol served by the External Market API, e.g. ``^IRX``).
    A series with no provider (``provider is None``) has no datasource yet.
    """
    client: (
        InvestingClient
        | ECBClient
        | ECBDataClient
        | BojClient
        | BlsClient
        | FredClient
        | EurostatClient
        | MarketApiMacroClient
    )
    if provider == "ecb":
        client = ECBDataClient() if url.startswith(ECBDataClient.BASE_URL) else ECBClient()
    elif provider == "boj":
        client = BojClient()
    elif provider == "bls":
        client = BlsClient()
    elif provider == "fred":
        client = FredClient()
    elif provider == "eurostat":
        client = EurostatClient()
    elif provider == "market-api":
        client = MarketApiMacroClient()
    elif provider == "investing-com":
        client = InvestingClient()
    else:
        raise MacroClientError(f"unknown macro provider: {provider!r}")
    try:
        return client.fetch(url)
    finally:
        client.close()
