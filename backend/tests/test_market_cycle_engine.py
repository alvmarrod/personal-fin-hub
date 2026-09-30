"""Tests for the Investment Market Cycle state engine.

The derived series are injected (the engine's data source is the derived layer,
already tested), so these tests exercise the state machine itself: edges,
signals, two-stage confirmation, tie-hold, entry signals, and the output shape.
"""

import sqlite3
import unittest
from datetime import date
from typing import Any
from unittest.mock import PropertyMock, patch

from services.config import Config
from services.derived_kpi_calc import DatedPoint, DatedSeries, Resolution, TrendDirection
from services.market_cycle_engine import (
    STATE_NAMES,
    CycleState,
    NotComputable,
    TransitionStatus,
    _status_for,
    evaluate,
    scope_keys,
)


def months(n: int, start: date = date(2020, 1, 1)) -> list[date]:
    out = []
    year, month = start.year, start.month
    for _ in range(n):
        out.append(date(year, month, 1))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return out


def direction_series(values: list[TrendDirection]) -> DatedSeries[TrendDirection]:
    points = tuple(DatedPoint(d, v) for d, v in zip(months(len(values)), values, strict=True))
    return DatedSeries(Resolution.MONTHLY, points)


def float_series(values: list[float]) -> DatedSeries[float]:
    points = tuple(DatedPoint(d, v) for d, v in zip(months(len(values)), values, strict=True))
    return DatedSeries(Resolution.MONTHLY, points)


def drive(series: dict) -> Any:
    """Patch the engine's derived/world series source with fixed series.

    The engine loads every input (levels and trends) through
    ``derived_kpi_svc.resolve_monthly``; a name not in ``series`` resolves to an
    empty series (levels absent => null metric values, no exception).
    """

    def side_effect(name, market, conn=None):
        return series.get(name, DatedSeries(Resolution.MONTHLY, ()))

    return patch("services.derived_kpi_svc.resolve_monthly", side_effect=side_effect)


def initial_state(state: int) -> Any:
    return patch.object(Config, "market_cycle_initial_state", new_callable=PropertyMock, return_value=state)


class TestStatusMapping(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(_status_for(0), TransitionStatus.INACTIVE)
        self.assertEqual(_status_for(1), TransitionStatus.EMERGING)
        self.assertEqual(_status_for(2), TransitionStatus.NEAR)
        self.assertEqual(_status_for(3), TransitionStatus.TRIGGERED)
        self.assertEqual(_status_for(9), TransitionStatus.TRIGGERED)


class EngineTestBase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def evaluate(self, scope="spain-eurozone"):
        return evaluate(scope, conn=self.conn)


class TestForwardCycle(EngineTestBase):
    """A scripted run moves 1→2→3→4→5→6→1 and ends in Low Real Rates."""

    def _series(self):
        inc, dec, stable = TrendDirection.INCREASING, TrendDirection.DECREASING, TrendDirection.STABLE
        policy = [stable] * 3 + [inc] * 6 + [dec] * 9
        inflation = [inc] * 9 + [stable] * 9
        real_level = [0.0] * 6 + [2.0] * 3 + [0.0] * 9
        real_trend = [inc] * 9 + [dec] * 9
        return {
            "policy_rate_trend": direction_series(policy),
            "inflation_rate_trend": direction_series(inflation),
            "real_interest_rate": float_series(real_level),
            "real_interest_rate_trend": direction_series(real_trend),
        }

    def test_full_cycle(self):
        with drive(self._series()):
            status = self.evaluate()
        # The machine walks 1→2→3→4→5→6→1; each step confirms once the
        # condition has held for 3 consecutive months, so it lands back in
        # Low Real Rates before the scripted window ends.
        self.assertEqual(status.current_state, CycleState.LOW_REAL_RATES)
        self.assertEqual(status.current_state_since, date(2021, 2, 1))
        self.assertFalse(status.ambiguous_confirmation)


class TestTwoStageConfirmation(EngineTestBase):
    def test_near_is_not_enough_to_commit(self):
        # Inflation increasing for only 2 months: Near, never Triggered -> state stays 1.
        inc = TrendDirection.INCREASING
        stable = TrendDirection.STABLE
        series = {
            "policy_rate_trend": direction_series([stable, stable]),
            "inflation_rate_trend": direction_series([inc, inc]),
            "real_interest_rate": float_series([0.0, 0.0]),
            "real_interest_rate_trend": direction_series([stable, stable]),
        }
        with drive(series):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.LOW_REAL_RATES)
        edge = status.active_transitions[0]
        self.assertEqual(edge.status, TransitionStatus.NEAR)


class TestReverseEdge(EngineTestBase):
    def _series(self):
        # In Cutting Cycle (6): cuts stop (policy stable) and real rates decline.
        dec, stable = TrendDirection.DECREASING, TrendDirection.STABLE
        return {
            "policy_rate_trend": direction_series([stable] * 4),
            "inflation_rate_trend": direction_series([stable] * 4),
            "real_interest_rate": float_series([0.5] * 4),  # not low -> forward 6->1 inactive
            "real_interest_rate_trend": direction_series([dec] * 4),
        }

    def test_reverse_fires_when_enabled(self):
        with initial_state(6), drive(self._series()):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.RISING_INFLATION)  # 6 -> 2

    def test_reverse_skipped_when_disabled(self):
        disabled = {"6->2": False, "5->4": True, "4->3": True, "3->2": True}
        disabled_patch = patch.object(
            Config, "market_cycle_reverse_edges_enabled", new_callable=PropertyMock, return_value=disabled
        )
        with initial_state(6), disabled_patch, drive(self._series()):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.CUTTING_CYCLE)  # held


class TestTieHold(EngineTestBase):
    def test_two_triggered_edges_hold_state(self):
        # In Hiking Cycle (3): both 3->4 (real rates high) and 3->2
        # (hikes stopped AND inflation increasing) are Triggered -> hold.
        inc, stable = TrendDirection.INCREASING, TrendDirection.STABLE
        series = {
            "policy_rate_trend": direction_series([stable] * 4),  # hikes stopped
            "inflation_rate_trend": direction_series([inc] * 4),
            "real_interest_rate": float_series([2.0] * 4),  # high
            "real_interest_rate_trend": direction_series([stable] * 4),
        }
        with initial_state(3), drive(series):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.HIKING_CYCLE)
        self.assertTrue(status.ambiguous_confirmation)
        triggered = [t for t in status.active_transitions if t.status is TransitionStatus.TRIGGERED]
        self.assertEqual(len(triggered), 2)


class TestEntrySignals(EngineTestBase):
    def test_high_real_rates_is_favourable(self):
        inc = TrendDirection.INCREASING
        series = {
            "policy_rate_trend": direction_series([inc] * 4),
            "inflation_rate_trend": direction_series([inc] * 4),
            "real_interest_rate": float_series([2.0] * 4),
            "real_interest_rate_trend": direction_series([inc] * 4),
        }
        with initial_state(4), drive(series):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.HIGH_REAL_RATES)
        self.assertEqual(status.entry_signals, "favourable")

    def test_first_rate_cut_is_strong(self):
        stable = TrendDirection.STABLE
        series = {
            "policy_rate_trend": direction_series([stable] * 4),
            "inflation_rate_trend": direction_series([stable] * 4),
            "real_interest_rate": float_series([0.0] * 4),
            "real_interest_rate_trend": direction_series([stable] * 4),
        }
        with initial_state(5), drive(series):
            status = self.evaluate()
        self.assertEqual(status.current_state, CycleState.FIRST_RATE_CUT)
        self.assertEqual(status.entry_signals, "strong")


class TestScopeAndOutput(EngineTestBase):
    def test_scope_keys_covers_wired_scopes(self):
        # Spain/Eurozone and USA have all inputs; Japan/Global do not.
        self.assertEqual(scope_keys(), ["spain-eurozone", "usa"])

    def test_not_computable_for_missing_scope(self):
        # Global aggregate has no wired inputs yet.
        with self.assertRaises(NotComputable):
            evaluate("global", conn=self.conn)

    def test_output_contract_shape(self):
        inc = TrendDirection.INCREASING
        series = {
            "policy_rate_trend": direction_series([inc] * 4),
            "inflation_rate_trend": direction_series([inc] * 4),
            "real_interest_rate": float_series([2.0] * 4),
            "real_interest_rate_trend": direction_series([inc] * 4),
        }
        with initial_state(4), drive(series):
            status = self.evaluate()
        payload = status.to_dict()
        self.assertEqual(
            set(payload),
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
        self.assertEqual(payload["current_state"], {"id": 4, "name": STATE_NAMES[CycleState.HIGH_REAL_RATES]})
        self.assertEqual(
            set(payload["active_transitions"][0]),
            {
                "source",
                "target",
                "status",
                "direction",
                "priority",
                "held_months",
                "required_months",
                "signals",
            },
        )


class TestSignalDiagnostics(EngineTestBase):
    """The output carries each signal's value, condition, formula, and progress."""

    @staticmethod
    def _series(real: float, policy_level: float, inflation_level: float) -> dict:
        inc = TrendDirection.INCREASING
        return {
            "policy_rate": float_series([policy_level] * 4),
            "inflation_rate": float_series([inflation_level] * 4),
            "policy_rate_trend": direction_series([inc] * 4),
            "inflation_rate_trend": direction_series([inc] * 4),
            "real_interest_rate": float_series([real] * 4),
            "real_interest_rate_trend": direction_series([inc] * 4),
        }

    def test_threshold_signal_exposes_value_condition_and_formula(self):
        # In Hiking Cycle: 3 -> 4 fires on real_rates_high. Real rate = 4 - 4 = 0,
        # below the configured high threshold (1.0), so the signal is not met.
        series = self._series(real=0.0, policy_level=4.0, inflation_level=4.0)
        with initial_state(3), drive(series):
            status = self.evaluate()
        payload = status.to_dict()
        edge = next(t for t in payload["active_transitions"] if t["target"] == STATE_NAMES[CycleState.HIGH_REAL_RATES])
        self.assertEqual(edge["required_months"], 3)
        self.assertEqual(edge["held_months"], 0)
        signal = edge["signals"][0]
        self.assertEqual(signal["code"], "real_rates_high")
        self.assertFalse(signal["met"])
        self.assertEqual(signal["value"], 0.0)
        self.assertEqual(signal["condition"], {"op": ">", "target": 1.0})
        self.assertEqual(signal["formula"]["code"], "real_rate")
        self.assertEqual(signal["formula"]["inputs"][0]["value"], 4.0)
        self.assertEqual(signal["formula"]["inputs"][1]["value"], 4.0)

    def test_metrics_block_lists_the_six_inputs(self):
        series = self._series(real=2.0, policy_level=4.0, inflation_level=2.0)
        with initial_state(4), drive(series):
            status = self.evaluate()
        metrics = status.to_dict()["metrics"]
        self.assertEqual(
            [metric["kpi"] for metric in metrics],
            [
                "inflation_rate",
                "inflation_rate_trend",
                "policy_rate",
                "policy_rate_trend",
                "real_interest_rate",
                "real_interest_rate_trend",
            ],
        )
        real = next(metric for metric in metrics if metric["kpi"] == "real_interest_rate")
        self.assertEqual(real["value"], 2.0)
        self.assertEqual(real["formula"]["code"], "real_rate")
        self.assertEqual(real["formula"]["inputs"][0]["value"], 4.0)
        trend = next(metric for metric in metrics if metric["kpi"] == "inflation_rate_trend")
        self.assertEqual(trend["kind"], "direction")
        self.assertEqual(trend["value"], TrendDirection.INCREASING.value)


if __name__ == "__main__":
    unittest.main()
