import sqlite3
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.health import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)


class TestHealth(unittest.TestCase):
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
