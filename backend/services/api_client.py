import logging
import time

import httpx

from services.api_resilience import (
    get_breaker,
    should_retry_http,
    sleep_between_attempts,
)
from services.config import config

logger = logging.getLogger(__name__)


class MarketAPIError(Exception):
    """Base exception for Market API errors."""

    pass


class MarketAPIUnavailable(MarketAPIError):
    """Raised when Market API is unavailable."""

    pass


class MarketAPINotFound(MarketAPIError):
    """Raised when symbol or field is not found."""

    pass


class MarketAPIClient:
    """Client for interacting with the external Market API."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = base_url or config.market_api_base_url
        self.timeout = timeout or config.market_api_timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def _request(self, method: str, path: str) -> dict:
        """Make a request to the Market API, retrying transient failures."""
        breaker = get_breaker(self.base_url)
        if not breaker.allow_request():
            logger.warning(
                "market_api circuit %s: %s %s (fail fast)",
                breaker.state.value,
                method,
                path,
            )
            raise MarketAPIUnavailable("Market API is unavailable (circuit open)")

        attempts = max(1, config.market_api_retry_attempts)
        for attempt in range(1, attempts + 1):
            start = time.monotonic()
            try:
                response = self._client.request(method, path)
                elapsed = time.monotonic() - start
                logger.debug("market_api %s %s → %s (%dms)", method, path, response.status_code, int(elapsed * 1000))
                response.raise_for_status()
                breaker.record_success()
                return response.json()
            except httpx.TransportError as e:
                if attempt < attempts:
                    logger.warning(
                        "market_api retry (%d/%d) %s %s: %s",
                        attempt,
                        attempts,
                        method,
                        path,
                        type(e).__name__,
                    )
                    sleep_between_attempts(
                        attempt,
                        config.market_api_retry_base_delay,
                        config.market_api_retry_max_delay,
                    )
                    continue
                breaker.record_failure()
                if isinstance(e, httpx.TimeoutException):
                    logger.warning("market_api timeout: %s %s (%.1fs)", method, path, time.monotonic() - start)
                    raise MarketAPIUnavailable("Market API request timed out") from None
                logger.warning("market_api unreachable: %s %s", method, path)
                raise MarketAPIUnavailable("Cannot connect to Market API") from None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise MarketAPINotFound(f"Resource not found: {path}") from e
                if should_retry_http(e.response.status_code):
                    if attempt < attempts:
                        logger.warning(
                            "market_api retry (%d/%d) %s %s → HTTP %d",
                            attempt,
                            attempts,
                            method,
                            path,
                            e.response.status_code,
                        )
                        sleep_between_attempts(
                            attempt,
                            config.market_api_retry_base_delay,
                            config.market_api_retry_max_delay,
                            e.response,
                        )
                        continue
                    breaker.record_failure()
                raise MarketAPIError(f"Market API error: {e}") from e

        raise MarketAPIUnavailable("Cannot connect to Market API")  # pragma: no cover - attempts >= 1

    def get_all(self, symbol: str) -> dict:
        """Fetch all available data for a symbol."""
        return self._request("GET", f"/symbol/{symbol}")

    def get_field(self, symbol: str, field: str) -> dict:
        """Fetch a specific field's value as JSON."""
        return self._request("GET", f"/symbol/{symbol}/{field}/")

    def get_raw_field(self, symbol: str, field: str) -> str:
        """Fetch a specific field's raw value."""
        response = self._client.get(f"/symbol/{symbol}/{field}/raw")
        response.raise_for_status()
        return response.text

    def get_price(self, symbol: str) -> dict:
        """Fetch current price for a symbol."""
        return self.get_field(symbol, "price")

    def health_check(self) -> bool:
        """Check if Market API is available — single attempt, short timeout.

        Bypasses the retry machinery because this is a health probe, not a
        data fetch. Docker healthcheck has a tight timeout and retries at
        the orchestration layer.
        """
        breaker = get_breaker(self.base_url)
        if not breaker.allow_request():
            return False
        try:
            self._client.get("/health", timeout=2.0).raise_for_status()
            return True
        except Exception:
            return False

    def close(self):
        """Close the HTTP client."""
        self._client.close()


# Module-level client instance
_client: MarketAPIClient | None = None


def get_market_client() -> MarketAPIClient:
    """Get or create the Market API client instance."""
    global _client
    if _client is None:
        _client = MarketAPIClient()
    return _client
