"""Tests for GET /analytics/investment-market-cycle (Phase 5)."""

import unittest
from datetime import date
from unittest.mock import PropertyMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from routes import analytics
from routes.deps import require_profile
from services.config import Config
from services.derived_kpi_calc import DatedPoint, DatedSeries, Resolution, TrendDirection
from services.market_cycle_engine import NotComputable

test_app = FastAPI()
test_app.include_router(analytics.router, prefix="/api/v1")
client = TestClient(test_app)

# A second app with the profile dependency, as main.py wires /analytics.
auth_app = FastAPI()
auth_app.include_router(analytics.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
auth_client = TestClient(auth_app)

PATH = "/api/v1/analytics/investment-market-cycle"

PAYLOAD = {
    "scope": "spain-eurozone",
    "current_state": {"id": 4, "name": "High Real Rates"},
    "current_state_since": "2026-01-15",
    "active_transitions": [
        {
            "source": "High Real Rates",
            "target": "First Rate Cut",
            "status": "Triggered",
            "direction": "Forward",
            "priority": 4,
            "held_months": 3,
            "required_months": 3,
            "signals": [
                {
                    "code": "first_cut_detected",
                    "metric": "policy_rate_trend",
                    "kind": "combination",
                    "met": True,
                    "value": None,
                    "unit": None,
                    "condition": None,
                    "formula": None,
                    "parts": [],
                }
            ],
        }
    ],
    "entry_signals": "favourable",
    "ambiguous_confirmation": False,
    "last_update": "2026-09-30T10:00:00+00:00",
    "metrics": [
        {
            "kpi": "inflation_rate",
            "kind": "level",
            "value": 3.0,
            "unit": "%",
            "prev_value": None,
            "delta": None,
            "formula": None,
        }
    ],
}


class _FakeStatus:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return self._payload


class TestMarketCycleEndpoint(unittest.TestCase):
    def test_returns_status_object(self):
        with patch("routes.analytics.evaluate", return_value=_FakeStatus(PAYLOAD)):
            response = client.get(PATH, params={"scope": "spain-eurozone"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), PAYLOAD)

    def test_unknown_scope_is_400(self):
        response = client.get(PATH, params={"scope": "mars"})
        self.assertEqual(response.status_code, 400)

    def test_not_computable_scope_is_400(self):
        with patch("routes.analytics.evaluate", side_effect=NotComputable("scope 'japan' lacks required inputs")):
            response = client.get(PATH, params={"scope": "japan"})
        self.assertEqual(response.status_code, 400)

    def test_missing_scope_is_422(self):
        response = client.get(PATH)
        self.assertEqual(response.status_code, 422)

    def test_requires_profile_header(self):
        response = auth_client.get(PATH, params={"scope": "spain-eurozone"})
        self.assertEqual(response.status_code, 401)


def _monthly(values):
    start_year, start_month = 2020, 1
    points = []
    year, month = start_year, start_month
    for value in values:
        points.append(DatedPoint(date(year, month, 1), value))
        month = month % 12 + 1
        year = year + 1 if month == 1 else year
    return tuple(points)


def _direction_series(values):
    return DatedSeries(Resolution.MONTHLY, _monthly(values))


def _float_series(values):
    return DatedSeries(Resolution.MONTHLY, _monthly(values))


class TestMarketCycleEndpointIntegration(unittest.TestCase):
    """Route → engine → Pydantic model, with the derived source stubbed."""

    def test_end_to_end_spain_eurozone(self):
        inc = TrendDirection.INCREASING
        series = {
            "policy_rate": _float_series([4.0] * 4),
            "inflation_rate": _float_series([2.0] * 4),
            "policy_rate_trend": _direction_series([inc] * 4),
            "inflation_rate_trend": _direction_series([inc] * 4),
            "real_interest_rate": _float_series([2.0] * 4),
            "real_interest_rate_trend": _direction_series([inc] * 4),
        }
        with (
            patch("services.derived_kpi_svc.resolve_monthly", side_effect=lambda name, market, conn=None: series[name]),
            patch.object(Config, "market_cycle_initial_state", new_callable=PropertyMock, return_value=4),
        ):
            response = client.get(PATH, params={"scope": "spain-eurozone"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["current_state"], {"id": 4, "name": "High Real Rates"})
        self.assertEqual(body["entry_signals"], "favourable")
        self.assertEqual(len(body["metrics"]), 6)
        self.assertEqual(
            set(body),
            {
                "scope",
                "current_state",
                "current_state_since",
                "active_transitions",
                "entry_signals",
                "ambiguous_confirmation",
                "last_update",
                "metrics",
            },
        )
        edge = body["active_transitions"][0]
        self.assertIn("held_months", edge)
        self.assertIn("signals", edge)


if __name__ == "__main__":
    unittest.main()
