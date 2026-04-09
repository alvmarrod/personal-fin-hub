import httpx
from typing import Any, Optional

from services.config import config


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

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = base_url or config.market_api_base_url
        self.timeout = timeout or config.market_api_timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def _request(self, method: str, path: str) -> dict:
        """Make a request to the Market API."""
        try:
            response = self._client.request(method, path)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise MarketAPIUnavailable("Cannot connect to Market API")
        except httpx.TimeoutException:
            raise MarketAPIUnavailable("Market API request timed out")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise MarketAPINotFound(f"Resource not found: {path}")
            raise MarketAPIError(f"Market API error: {e}")

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
        """Check if Market API is available."""
        try:
            self._request("GET", "/health")
            return True
        except MarketAPIError:
            return False

    def close(self):
        """Close the HTTP client."""
        self._client.close()


# Module-level client instance
_client: Optional[MarketAPIClient] = None


def get_market_client() -> MarketAPIClient:
    """Get or create the Market API client instance."""
    global _client
    if _client is None:
        _client = MarketAPIClient()
    return _client
