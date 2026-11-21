import unittest
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from models import (
    StrategyDrift,
    StrategyDriftBucket,
    StrategyDriftResidual,
    StrategyHistory,
    StrategyHistoryPoint,
    StrategyTargetSet,
)
from routes.strategy import router
from services.analytics_svc import AnalyticsError
from services.strategy_svc import StrategyExists, StrategyNotFound

app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)

TARGETS: dict[str, float] = {"equities": 55.0, "bonds": 30.0, "cash": 15.0, "real_estate": 0.0, "gold": 0.0}
BODY = {"effective_from": "2026-01-01", "targets": TARGETS}


def _set(effective_from: str = "2026-01-01") -> StrategyTargetSet:
    return StrategyTargetSet(
        effective_from=date.fromisoformat(effective_from),
        targets=TARGETS,
        updated_at="2026-01-01 10:00:00",
    )


def _drift() -> StrategyDrift:
    return StrategyDrift(
        effective_from=date(2026, 1, 1),
        as_of=date(2026, 11, 21),
        total=1000.0,
        rate_missing=False,
        buckets=[
            StrategyDriftBucket(
                bucket="equities",
                target_pct=55,
                value=600.0,
                share_pct=60.0,
                drift_pp=5.0,
                amount_to_move=-50.0,
            )
        ],
        unassigned=StrategyDriftResidual(value=0.0, share_pct=0.0),
    )


class StrategyRoutesTest(unittest.TestCase):
    def test_list_sets(self):
        with patch("routes.strategy.list_sets", return_value=[_set()]):
            resp = client.get("/api/v1/strategy")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["effective_from"], "2026-01-01")
        self.assertEqual(resp.json()[0]["targets"]["equities"], 55)

    def test_create_set(self):
        with patch("routes.strategy.create", return_value=_set()) as create:
            resp = client.post("/api/v1/strategy", json=BODY)

        self.assertEqual(resp.status_code, 201)
        create.assert_called_once()

    def test_create_rejects_a_bad_sum(self):
        resp = client.post(
            "/api/v1/strategy",
            json={"effective_from": "2026-01-01", "targets": {**TARGETS, "cash": 0}},
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_rejects_a_missing_bucket(self):
        body = {"effective_from": "2026-01-01", "targets": {"equities": 100}}
        self.assertEqual(client.post("/api/v1/strategy", json=body).status_code, 422)

    def test_create_rejects_a_duplicate_date(self):
        with patch("routes.strategy.create", side_effect=StrategyExists("exists")):
            resp = client.post("/api/v1/strategy", json=BODY)
        self.assertEqual(resp.status_code, 409)

    def test_history(self):
        result = StrategyHistory(
            points=[
                StrategyHistoryPoint(date="2026-06-01", bucket="equities", value=550.0, share_pct=50.0, target_pct=55.0)
            ]
        )
        with patch("routes.strategy.history", return_value=result) as history:
            resp = client.get("/api/v1/strategy/history?start_date=2026-01-01&end_date=2026-12-31&display_currency=EUR")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["points"][0]["target_pct"], 55.0)
        history.assert_called_once_with("2026-01-01", "2026-12-31", "month", "EUR")

    def test_history_rejects_a_bad_interval(self):
        with patch("routes.strategy.history", side_effect=AnalyticsError("bad interval")):
            resp = client.get("/api/v1/strategy/history?start_date=2026-01-01&end_date=2026-12-31")

        self.assertEqual(resp.status_code, 400)

    def test_replace_missing_set(self):
        with patch("routes.strategy.replace", side_effect=StrategyNotFound("missing")):
            resp = client.put("/api/v1/strategy/2026-01-01", json=BODY)
        self.assertEqual(resp.status_code, 404)

    def test_delete_set(self):
        with patch("routes.strategy.delete") as delete:
            resp = client.delete("/api/v1/strategy/2026-01-01")
        self.assertEqual(resp.status_code, 204)
        delete.assert_called_once()

    def test_delete_missing_set(self):
        with patch("routes.strategy.delete", side_effect=StrategyNotFound("missing")):
            resp = client.delete("/api/v1/strategy/2026-01-01")
        self.assertEqual(resp.status_code, 404)

    def test_drift(self):
        with patch("routes.strategy.drift", return_value=_drift()) as drift:
            resp = client.get("/api/v1/strategy/drift?display_currency=EUR")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["effective_from"], "2026-01-01")
        self.assertEqual(resp.json()["buckets"][0]["drift_pp"], 5.0)
        drift.assert_called_once_with("EUR")


if __name__ == "__main__":
    unittest.main()
