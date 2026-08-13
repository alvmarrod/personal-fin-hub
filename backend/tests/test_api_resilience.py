import concurrent.futures
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from services import api_client, api_resilience
from services.api_client import MarketAPIClient, MarketAPIError, MarketAPINotFound, MarketAPIUnavailable

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def _config(attempts=3, base=0.5, maximum=10.0):
    return SimpleNamespace(
        market_api_retry_attempts=attempts,
        market_api_retry_base_delay=base,
        market_api_retry_max_delay=maximum,
    )


def _full_config(attempts=3, base=0.5, maximum=10.0, threshold=5, cooldown=60.0):
    return SimpleNamespace(
        market_api_retry_attempts=attempts,
        market_api_retry_base_delay=base,
        market_api_retry_max_delay=maximum,
        market_api_circuit_failure_threshold=threshold,
        market_api_circuit_cooldown_seconds=cooldown,
    )


class _FakeClock:
    """Deterministic monotonic clock for circuit-breaker cooldown tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _OpenBreaker:
    """Fake breaker that reports an open circuit."""

    def is_open(self) -> bool:
        return True


class _ClosedBreaker:
    """Fake breaker that reports a closed circuit."""

    def is_open(self) -> bool:
        return False


def _in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def _success_response(payload):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


def _http_error(status_code, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"HTTP {status_code}", request=MagicMock(), response=response
    )
    return response


class TestRetryPolicy(unittest.TestCase):
    """Unit tests for the retry policy helpers in services/api_resilience.py."""

    def test_backoff_delay_exponential(self):
        self.assertEqual(api_resilience.backoff_delay(1, 0.5, 10), 0.5)
        self.assertEqual(api_resilience.backoff_delay(2, 0.5, 10), 1.0)
        self.assertEqual(api_resilience.backoff_delay(3, 0.5, 10), 2.0)

    def test_backoff_delay_capped(self):
        self.assertEqual(api_resilience.backoff_delay(5, 1, 4), 4.0)
        self.assertEqual(api_resilience.backoff_delay(10, 0.5, 10), 10.0)

    def test_jitter_within_bounds(self):
        for _ in range(50):
            value = api_resilience.jitter(1.0)
            self.assertGreaterEqual(value, 0.8)
            self.assertLessEqual(value, 1.2)

    def test_retry_after_seconds_parsed(self):
        response = MagicMock()
        response.headers = {"Retry-After": "5"}
        self.assertEqual(api_resilience.retry_after_seconds(response), 5)

    def test_retry_after_seconds_capped(self):
        response = MagicMock()
        response.headers = {"Retry-After": "120"}
        self.assertEqual(api_resilience.retry_after_seconds(response), 60)

    def test_retry_after_seconds_missing_or_invalid(self):
        response = MagicMock()
        response.headers = {}
        self.assertIsNone(api_resilience.retry_after_seconds(response))
        response.headers = {"Retry-After": "soon"}
        self.assertIsNone(api_resilience.retry_after_seconds(response))

    def test_should_retry_http(self):
        self.assertTrue(api_resilience.should_retry_http(500))
        self.assertTrue(api_resilience.should_retry_http(503))
        self.assertTrue(api_resilience.should_retry_http(429))
        self.assertFalse(api_resilience.should_retry_http(400))
        self.assertFalse(api_resilience.should_retry_http(404))


class TestRetryBehaviour(unittest.TestCase):
    """Retry behaviour of MarketAPIClient._request."""

    def setUp(self):
        api_resilience.reset_breakers()
        self.mock_client_patcher = patch("services.api_client.httpx.Client")
        self.MockClient = self.mock_client_patcher.start()
        self.mock_instance = MagicMock()
        self.MockClient.return_value = self.mock_instance
        self.sleep_patcher = patch("services.api_client.sleep_between_attempts")
        self.mock_sleep = self.sleep_patcher.start()
        self.config_patcher = patch.object(api_client, "config", _config())
        self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.sleep_patcher.stop()
        self.mock_client_patcher.stop()
        api_resilience.reset_breakers()

    def _client(self):
        return MarketAPIClient(base_url="http://test", timeout=30)

    def test_transient_error_retried_until_attempts(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 3)

    def test_success_after_transient_failure(self):
        self.mock_instance.request.side_effect = [
            httpx.TimeoutException(message="slow", request=MagicMock()),
            _success_response({"price": 150.25}),
        ]
        result = self._client().get_price("AAPL")
        self.assertEqual(result, {"price": 150.25})
        self.assertEqual(self.mock_instance.request.call_count, 2)

    def test_404_not_retried(self):
        self.mock_instance.request.return_value = _http_error(404)
        with self.assertRaises(MarketAPINotFound):
            self._client().get_field("INVALID", "ROE")
        self.assertEqual(self.mock_instance.request.call_count, 1)

    def test_other_4xx_not_retried(self):
        self.mock_instance.request.return_value = _http_error(400)
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 1)

    def test_500_retried_then_error(self):
        self.mock_instance.request.return_value = _http_error(500)
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 3)

    def test_429_retried(self):
        self.mock_instance.request.return_value = _http_error(429)
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 3)

    def test_backoff_sequence(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_sleep.call_count, 2)
        attempt_calls = [call.args[0] for call in self.mock_sleep.call_args_list]
        self.assertEqual(attempt_calls, [1, 2])

    def test_retry_attempts_one_disables_retry(self):
        self.config_patcher.stop()
        self.config_patcher = patch.object(api_client, "config", _config(attempts=1))
        self.config_patcher.start()
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 1)
        self.assertEqual(self.mock_sleep.call_count, 0)

    def test_health_returns_false_after_failure(self):
        self.mock_instance.get.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        self.assertFalse(self._client().health_check())


class TestCircuitBreaker(unittest.TestCase):
    """Unit tests for the CircuitBreaker state machine."""

    def test_starts_closed(self):
        breaker = api_resilience.CircuitBreaker(failure_threshold=5, cooldown_seconds=60, now=_FakeClock())
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        self.assertFalse(breaker.is_open())
        self.assertTrue(breaker.allow_request())
        self.assertEqual(breaker.consecutive_failures, 0)

    def test_opens_after_threshold_failures(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=3, cooldown_seconds=60, now=clock)
        breaker.record_failure()
        breaker.record_failure()
        self.assertFalse(breaker.is_open())
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)
        self.assertTrue(breaker.is_open())
        self.assertFalse(breaker.allow_request())

    def test_open_denies_until_cooldown_elapses(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=1, cooldown_seconds=60, now=clock)
        breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)
        self.assertFalse(breaker.allow_request())
        clock.advance(59.9)
        self.assertFalse(breaker.allow_request())
        clock.advance(0.1)
        self.assertTrue(breaker.allow_request())

    def test_half_open_admits_single_trial(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=1, cooldown_seconds=60, now=clock)
        breaker.record_failure()
        clock.advance(60)
        self.assertTrue(breaker.allow_request())
        self.assertIs(breaker.state, api_resilience.CircuitState.HALF_OPEN)
        self.assertFalse(breaker.allow_request())
        self.assertFalse(breaker.allow_request())

    def test_half_open_success_recovers(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=2, cooldown_seconds=60, now=clock)
        breaker.record_failure()
        breaker.record_failure()
        clock.advance(60)
        self.assertTrue(breaker.allow_request())
        breaker.record_success()
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        self.assertFalse(breaker.is_open())
        self.assertEqual(breaker.consecutive_failures, 0)
        self.assertTrue(breaker.allow_request())

    def test_half_open_failure_reopens_circuit(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=2, cooldown_seconds=60, now=clock)
        breaker.record_failure()
        breaker.record_failure()
        clock.advance(60)
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)
        clock.advance(59)
        self.assertFalse(breaker.allow_request())
        clock.advance(1)
        self.assertTrue(breaker.allow_request())

    def test_success_resets_failure_counter(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=5, cooldown_seconds=60, now=clock)
        for _ in range(4):
            breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        breaker.record_success()
        for _ in range(4):
            breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        breaker.record_failure()
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)

    def test_thread_safe_under_concurrent_failures(self):
        clock = _FakeClock()
        breaker = api_resilience.CircuitBreaker(failure_threshold=10, cooldown_seconds=60, now=clock)
        errors: list[BaseException] = []

        def hammer() -> None:
            try:
                for _ in range(5):
                    breaker.record_failure()
                breaker.allow_request()
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(hammer) for _ in range(8)]
            for future in futures:
                future.result()

        self.assertEqual(errors, [])
        self.assertEqual(breaker.consecutive_failures, 10)
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)
        self.assertFalse(breaker.allow_request())

    def test_breaker_shared_per_base_url(self):
        api_resilience.reset_breakers()
        a1 = api_resilience.get_breaker("http://one")
        a2 = api_resilience.get_breaker("http://one")
        b = api_resilience.get_breaker("http://two")
        self.assertIs(a1, a2)
        self.assertIsNot(a1, b)

    def test_config_defaults_when_absent(self):
        from services.config import config as real_config

        saved = real_config._data
        assert saved is not None
        real_config._data = {k: v for k, v in saved.items() if k != "market_api"}
        try:
            self.assertEqual(real_config.market_api_circuit_failure_threshold, 5)
            self.assertEqual(real_config.market_api_circuit_cooldown_seconds, 60.0)
        finally:
            real_config._data = saved

    def test_config_keys_present(self):
        from services.config import config as real_config

        self.assertEqual(real_config.market_api_circuit_failure_threshold, 5)
        self.assertEqual(real_config.market_api_circuit_cooldown_seconds, 60.0)


class TestCircuitIntegration(unittest.TestCase):
    """Circuit breaker behaviour of MarketAPIClient._request."""

    def setUp(self):
        api_resilience.reset_breakers()
        self.config_patcher = patch.object(api_client, "config", _full_config(threshold=2))
        self.config_patcher.start()
        self.breaker_config_patcher = patch.object(api_resilience, "config", _full_config(threshold=2))
        self.breaker_config_patcher.start()
        self.mock_client_patcher = patch("services.api_client.httpx.Client")
        self.MockClient = self.mock_client_patcher.start()
        self.mock_instance = MagicMock()
        self.MockClient.return_value = self.mock_instance
        self.sleep_patcher = patch("services.api_client.sleep_between_attempts")
        self.mock_sleep = self.sleep_patcher.start()

    def tearDown(self):
        self.mock_client_patcher.stop()
        self.sleep_patcher.stop()
        self.breaker_config_patcher.stop()
        self.config_patcher.stop()
        api_resilience.reset_breakers()

    def _client(self):
        return MarketAPIClient(base_url="http://circuit", timeout=30)

    def _set_threshold(self, threshold):
        self.config_patcher.stop()
        self.config_patcher = patch.object(api_client, "config", _full_config(threshold=threshold))
        self.config_patcher.start()
        self.breaker_config_patcher.stop()
        self.breaker_config_patcher = patch.object(api_resilience, "config", _full_config(threshold=threshold))
        self.breaker_config_patcher.start()
        api_resilience.reset_breakers()

    def test_open_circuit_fails_fast_without_http(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        for _ in range(2):
            with self.assertRaises(MarketAPIUnavailable):
                self._client().get_price("AAPL")
        breaker = api_resilience.get_breaker("http://circuit")
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)
        calls_before = self.mock_instance.request.call_count
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, calls_before)

    def test_success_records_and_resets_breaker(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        breaker = api_resilience.get_breaker("http://circuit")
        self.assertEqual(breaker.consecutive_failures, 1)
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        self.mock_instance.request.side_effect = [_success_response({"price": 1.0})]
        result = self._client().get_price("AAPL")
        self.assertEqual(result, {"price": 1.0})
        self.assertEqual(breaker.consecutive_failures, 0)
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)

    def test_consecutive_transport_failures_trip_breaker(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        breaker = api_resilience.get_breaker("http://circuit")
        self.assertEqual(breaker.consecutive_failures, 2)
        self.assertIs(breaker.state, api_resilience.CircuitState.OPEN)

    def test_5xx_exhaustion_trips_breaker(self):
        self.mock_instance.request.return_value = _http_error(500)
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        self.assertIs(api_resilience.get_breaker("http://circuit").state, api_resilience.CircuitState.OPEN)

    def test_404_does_not_trip_breaker(self):
        self._set_threshold(1)
        self.mock_instance.request.return_value = _http_error(404)
        with self.assertRaises(MarketAPINotFound):
            self._client().get_field("INVALID", "ROE")
        breaker = api_resilience.get_breaker("http://circuit")
        self.assertEqual(breaker.consecutive_failures, 0)
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)
        self.assertFalse(breaker.is_open())

    def test_other_4xx_does_not_trip_breaker(self):
        self._set_threshold(1)
        self.mock_instance.request.return_value = _http_error(400)
        with self.assertRaises(MarketAPIError):
            self._client().get_price("AAPL")
        breaker = api_resilience.get_breaker("http://circuit")
        self.assertEqual(breaker.consecutive_failures, 0)
        self.assertIs(breaker.state, api_resilience.CircuitState.CLOSED)

    def test_retry_still_applies_while_closed(self):
        self._set_threshold(5)
        self.mock_instance.request.side_effect = httpx.ConnectError(message="down", request=MagicMock())
        with self.assertRaises(MarketAPIUnavailable):
            self._client().get_price("AAPL")
        self.assertEqual(self.mock_instance.request.call_count, 3)
        self.assertEqual(self.mock_sleep.call_count, 2)


class TestSyncFailFast(unittest.TestCase):
    """POST /market/sync-prices and POST /currencies/sync short-circuit on an open circuit."""

    def setUp(self):
        from routes.currencies import router as currencies_router
        from routes.market import router as market_router

        app = FastAPI()
        app.include_router(market_router, prefix="/api/v1")
        app.include_router(currencies_router, prefix="/api/v1")
        self.client = TestClient(app)

        self.conn = _in_memory_db()
        self.market_db_patcher = patch("services.market_sync_svc.get_db", return_value=self.conn)
        self.market_db_patcher.start()
        self.currency_db_patcher = patch("services.currency_svc.get_db", return_value=self.conn)
        self.currency_db_patcher.start()

    def tearDown(self):
        self.market_db_patcher.stop()
        self.currency_db_patcher.stop()
        self.conn.close()
        api_resilience.reset_breakers()

    def _seed_price_assets(self):
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, name) VALUES ('AAPL', 'AAPL', 'STOCK', 'Apple')"
        )
        self.conn.execute("INSERT INTO portfolio_assets (market_code, is_active) VALUES ('AAPL', 1)")

    def _seed_rates(self):
        queries.create_self_rate(self.conn, "EUR", datetime(2025, 1, 1))
        queries.create_self_rate(self.conn, "USD", datetime(2025, 1, 1))

    def test_sync_prices_short_circuits_when_open(self):
        self._seed_price_assets()
        with (
            patch("services.market_sync_svc.get_breaker", return_value=_OpenBreaker()),
            patch("services.market_sync_svc.get_market_client") as mock_get_client,
        ):
            resp = self.client.post("/api/v1/market/sync-prices")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["circuit_open"])
        self.assertEqual(data["synced"], 0)
        self.assertEqual(data["skipped"], [{"market_code": "AAPL"}])
        mock_get_client.return_value.get_all.assert_not_called()

    def test_sync_rates_short_circuits_when_open(self):
        self._seed_rates()
        with (
            patch("services.currency_svc.get_breaker", return_value=_OpenBreaker()),
            patch("services.currency_svc.get_market_client") as mock_get_client,
        ):
            resp = self.client.post("/api/v1/currencies/sync")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["circuit_open"])
        self.assertEqual(data["total_rates"], 0)
        self.assertEqual(data["skipped"], [{"code": "EUR", "base_code": "USD"}])
        mock_get_client.return_value.get_all.assert_not_called()

    def test_sync_prices_closed_circuit_keeps_shape(self):
        self._seed_price_assets()
        mock_client = MagicMock()
        mock_client.get_all.return_value = {"price": 150.25, "history": {}}
        with (
            patch("services.market_sync_svc.get_breaker", return_value=_ClosedBreaker()),
            patch("services.market_sync_svc.get_market_client", return_value=mock_client),
        ):
            resp = self.client.post("/api/v1/market/sync-prices")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["synced"], 1)
        self.assertEqual(data["results"], [{"market_code": "AAPL", "price": 150.25}])
        self.assertNotIn("circuit_open", data)
        self.assertNotIn("skipped", data)

    def test_sync_rates_closed_circuit_keeps_shape(self):
        self._seed_rates()
        mock_client = MagicMock()
        mock_client.get_all.return_value = {
            "symbol": "EURUSD=X",
            "history": {"2025-06-01 00:00:00+00:00": {"Close": 1.055}},
        }
        with (
            patch("services.currency_svc.get_breaker", return_value=_ClosedBreaker()),
            patch("services.currency_svc.get_market_client", return_value=mock_client),
        ):
            resp = self.client.post("/api/v1/currencies/sync")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["synced"])
        self.assertEqual(data["total_rates"], 1)
        self.assertNotIn("circuit_open", data)
        self.assertNotIn("skipped", data)

    def test_sync_prices_skips_manual_tracked_assets(self):
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, name) VALUES ('GOLD', 'GOLD', 'FUND', 'Gold')"
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active, tracking_mode) VALUES ('GOLD', 1, 'manual')"
        )
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, name) VALUES ('AAPL', 'AAPL', 'STOCK', 'Apple')"
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active, tracking_mode) VALUES ('AAPL', 1, 'auto')"
        )

        mock_client = MagicMock()
        mock_client.get_all.return_value = {"price": 150.25, "history": {}}
        with (
            patch("services.market_sync_svc.get_breaker", return_value=_ClosedBreaker()),
            patch("services.market_sync_svc.get_market_client", return_value=mock_client),
        ):
            resp = self.client.post("/api/v1/market/sync-prices")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["synced"], 1, "Only the auto-tracked asset should be synced")
        self.assertEqual(data["results"], [{"market_code": "AAPL", "price": 150.25}])
        mock_client.get_all.assert_called_once_with("AAPL")

    def test_sync_prices_skips_fresh_symbols(self):
        self._seed_price_assets()
        self.conn.execute(
            "UPDATE market_assets SET last_synced_at = ? WHERE market_code = 'AAPL'",
            (datetime.now(UTC).isoformat(),),
        )
        mock_client = MagicMock()
        with (
            patch("services.market_sync_svc.get_breaker", return_value=_ClosedBreaker()),
            patch("services.market_sync_svc.get_market_client", return_value=mock_client),
        ):
            resp = self.client.post("/api/v1/market/sync-prices?full=false&pace=0&max_age_hours=1")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["synced"], 0, "Freshly-synced symbol should be skipped")
        mock_client.get_all.assert_not_called()

    def test_sync_prices_full_ignores_freshness(self):
        self._seed_price_assets()
        self.conn.execute(
            "UPDATE market_assets SET last_synced_at = ? WHERE market_code = 'AAPL'",
            (datetime.now(UTC).isoformat(),),
        )
        mock_client = MagicMock()
        mock_client.get_all.return_value = {"price": 150.25, "history": {}}
        with (
            patch("services.market_sync_svc.get_breaker", return_value=_ClosedBreaker()),
            patch("services.market_sync_svc.get_market_client", return_value=mock_client),
        ):
            resp = self.client.post("/api/v1/market/sync-prices?full=true&pace=0")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["synced"], 1, "Full refresh ignores freshness")
        mock_client.get_all.assert_called_once_with("AAPL")


if __name__ == "__main__":
    unittest.main()
