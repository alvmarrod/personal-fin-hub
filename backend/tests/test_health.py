import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.health import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)


class TestHealth(unittest.TestCase):
    def setUp(self):
        from services import api_resilience

        api_resilience.reset_breakers()

    def tearDown(self):
        from services import api_resilience

        api_resilience.reset_breakers()

    def test_healthy(self):
        with patch("routes.health.MarketAPIClient.health_check", return_value=True):
            resp = client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["checks"]["database"], "ok")
            self.assertEqual(data["checks"]["market_api"], "ok")

    def test_degraded_when_api_unreachable(self):
        with patch(
            "routes.health.MarketAPIClient.health_check",
            return_value=False,
        ):
            resp = client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "degraded")
            self.assertEqual(data["checks"]["market_api"], "unreachable")

    def test_unhealthy_when_db_fails(self):
        with patch("routes.health.get_db", side_effect=sqlite3.OperationalError("boom")):
            resp = client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertIn("error", data["checks"]["database"])

    def test_degraded_when_api_raises(self):
        with patch(
            "routes.health.MarketAPIClient.health_check",
            side_effect=ConnectionError("timeout"),
        ):
            resp = client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "degraded")
            self.assertIn("error", data["checks"]["market_api"])


class TestHealthMarketData(unittest.TestCase):
    """market_data_last_updated = newest stored price timestamp."""

    SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

    def _db_with_prices(self, timestamps):
        def fake_get_db():
            import sqlite3

            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.executescript(Path(self.SCHEMA_PATH).read_text())
            for ts in timestamps:
                conn.execute(
                    "INSERT INTO prices (market_code, timestamp, price, provider) VALUES (?, ?, ?, ?)",
                    ("AAPL.US", ts, 100.0, "stooq"),
                )
            return conn

        return fake_get_db

    def test_reports_newest_price_timestamp(self):
        with (
            patch("routes.health.MarketAPIClient.health_check", return_value=True),
            patch(
                "routes.health.get_db", side_effect=self._db_with_prices(["2025-01-01T00:00:00", "2025-06-01T12:00:00"])
            ),
        ):
            resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["checks"]["market_data_last_updated"], "2025-06-01T12:00:00")

    def test_reports_null_when_no_prices(self):
        with (
            patch("routes.health.MarketAPIClient.health_check", return_value=True),
            patch("routes.health.get_db", side_effect=self._db_with_prices([])),
        ):
            resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["checks"]["market_data_last_updated"])


class TestHealthCircuit(unittest.TestCase):
    def setUp(self):
        from services import api_resilience
        from services.config import config as real_config

        api_resilience.reset_breakers()
        self.base_url = real_config.market_api_base_url
        self.threshold = real_config.market_api_circuit_failure_threshold

    def tearDown(self):
        from services import api_resilience

        api_resilience.reset_breakers()

    def test_reports_closed_circuit_and_null_last_success(self):
        with patch("routes.health.MarketAPIClient.health_check", return_value=True):
            resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        checks = resp.json()["checks"]
        self.assertEqual(checks["market_api_circuit"], "closed")
        self.assertIsNone(checks["market_api_last_success_at"])

    def test_reports_last_success_at_iso(self):
        from datetime import UTC, datetime

        from services import api_resilience

        breaker = api_resilience.get_breaker(self.base_url)
        breaker.record_success()
        with patch("routes.health.MarketAPIClient.health_check", return_value=True):
            resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        last = resp.json()["checks"]["market_api_last_success_at"]
        self.assertIsInstance(last, str)
        self.assertEqual(datetime.fromisoformat(last).tzinfo, UTC)
        self.assertEqual(last, breaker.last_success_at)

    def test_open_circuit_fails_fast_with_zero_http(self):
        from services import api_resilience

        breaker = api_resilience.get_breaker(self.base_url)
        for _ in range(self.threshold):
            breaker.record_failure()
        self.assertEqual(breaker.state, api_resilience.CircuitState.OPEN)

        with patch("services.api_client.httpx.Client") as mock_client:
            instance = mock_client.return_value
            resp = client.get("/api/v1/health")

        self.assertEqual(resp.status_code, 200)
        checks = resp.json()["checks"]
        self.assertEqual(checks["market_api"], "unreachable")
        self.assertEqual(checks["market_api_circuit"], "open")
        instance.request.assert_not_called()
