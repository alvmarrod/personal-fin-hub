"""Tests for the derived macro layer (calculations + registry/access)."""

import sqlite3
import unittest
from datetime import date
from pathlib import Path

from services.derived_kpi_calc import (
    DatedPoint,
    DatedSeries,
    Resolution,
    TrendDirection,
    real_rate,
    slope_step,
    to_monthly,
)
from services.derived_kpi_svc import (
    DerivedNotDefined,
    ValueKind,
    derived_kpi,
    get_definition,
    latest_derived_kpi,
    list_derived_kpis,
    market_keys,
)
from services.world_kpi_svc import MARKET_JAPAN, MARKET_SPAIN_EUROZONE, MARKET_USA

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def series(resolution, *items) -> DatedSeries[float]:
    """Build a series from alternating date-tuple, value args."""
    points = [DatedPoint(date(*items[i]), items[i + 1]) for i in range(0, len(items), 2)]
    return DatedSeries(resolution, tuple(points))


class TestToMonthly(unittest.TestCase):
    def test_monthly_passthrough(self):
        s = series(Resolution.MONTHLY, (2024, 1, 1), 1.0)
        self.assertIs(to_monthly(s), s)

    def test_event_forward_filled_to_month_end(self):
        s = series(
            Resolution.EVENT,
            (2024, 6, 12),
            0.5,
            (2024, 9, 18),
            0.75,
        )
        monthly = to_monthly(s, as_of=date(2024, 10, 15))
        self.assertEqual(monthly.resolution, Resolution.MONTHLY)
        self.assertEqual(
            [(p.obs_date, p.value) for p in monthly.points],
            [
                (date(2024, 6, 30), 0.5),
                (date(2024, 7, 31), 0.5),
                (date(2024, 8, 31), 0.5),
                (date(2024, 9, 30), 0.75),
                (date(2024, 10, 15), 0.75),  # current/partial month uses as_of
            ],
        )

    def test_empty_series(self):
        s = series(Resolution.EVENT)
        self.assertEqual(to_monthly(s, as_of=date(2024, 1, 1)).points, ())


class TestSlopeStep(unittest.TestCase):
    def test_directions(self):
        s = series(
            Resolution.MONTHLY,
            (2025, 1, 31),
            2.0,
            (2025, 2, 28),
            1.75,  # decreasing
            (2025, 3, 31),
            1.75,  # stable
            (2025, 4, 30),
            2.0,  # increasing
        )
        directions = [p.value for p in slope_step(s).points]
        self.assertEqual(
            directions,
            [TrendDirection.DECREASING, TrendDirection.STABLE, TrendDirection.INCREASING],
        )
        # First point has no predecessor.
        self.assertEqual(slope_step(s).points[0].obs_date, date(2025, 2, 28))

    def test_float_noise_is_stable(self):
        s = series(
            Resolution.MONTHLY,
            (2025, 1, 31),
            1.0,
            (2025, 2, 28),
            1.0 + 1e-12,  # representation noise, not a real change
        )
        self.assertEqual(slope_step(s).points[0].value, TrendDirection.STABLE)

    def test_real_change_is_noticeable(self):
        s = series(
            Resolution.MONTHLY,
            (2025, 1, 31),
            1.0,
            (2025, 2, 28),
            1.0 + 1e-6,  # above the noise floor -> a real change
        )
        self.assertEqual(slope_step(s).points[0].value, TrendDirection.INCREASING)

    def test_deadband(self):
        s = series(
            Resolution.MONTHLY,
            (2025, 1, 31),
            1.0,
            (2025, 2, 28),
            1.05,
        )
        self.assertEqual(slope_step(s, deadband=0.1).points[0].value, TrendDirection.STABLE)


class TestRealRate(unittest.TestCase):
    def test_aligned_by_month(self):
        policy = series(
            Resolution.MONTHLY,
            (2025, 6, 30),
            2.0,
            (2025, 7, 31),
            1.75,
        )
        inflation = series(
            Resolution.MONTHLY,
            (2025, 6, 30),
            2.5,
            (2025, 8, 31),
            2.0,  # 2025-07 missing -> no point for that month
        )
        result = real_rate(policy, inflation)
        self.assertEqual(
            [(p.obs_date, p.value) for p in result.points],
            [(date(2025, 6, 30), -0.5)],
        )


def seed_macro(conn, slug, provider, points):
    conn.execute("INSERT INTO macro_series (slug, provider, name) VALUES (?, ?, ?)", (slug, provider, slug))
    conn.executemany(
        "INSERT INTO macro_series_observations (slug, obs_date, value) VALUES (?, ?, ?)",
        [(slug, d.isoformat(), v) for d, v in points],
    )
    conn.commit()


class TestDerivedRegistry(unittest.TestCase):
    def test_lists_kpis(self):
        self.assertEqual(
            list_derived_kpis(),
            [
                "inflation_rate_trend",
                "m2_growth_trend",
                "policy_rate_trend",
                "real_interest_rate",
                "real_interest_rate_trend",
            ],
        )

    def test_markets_are_intersection_of_inputs(self):
        # policy_rate exists for japan + spain-eurozone.
        self.assertEqual(market_keys("policy_rate_trend"), [MARKET_JAPAN, MARKET_SPAIN_EUROZONE])
        # real rate needs policy_rate AND inflation_rate -> spain-eurozone only.
        self.assertEqual(market_keys("real_interest_rate"), [MARKET_SPAIN_EUROZONE])

    def test_value_kinds(self):
        self.assertEqual(get_definition("m2_growth_trend").value_kind, ValueKind.DIRECTION)
        self.assertEqual(get_definition("real_interest_rate").value_kind, ValueKind.NUMERIC)


class TestDerivedAccess(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_PATH.read_text())
        # Policy rate (event/step), two hikes.
        seed_macro(
            self.conn,
            "boj-policy-rate",
            "boj",
            [(date(2024, 6, 12), 0.5), (date(2024, 9, 18), 0.75)],
        )
        # USA CPI index (level) -> YoY world KPI (two YoY points -> one slope point).
        seed_macro(
            self.conn,
            "usa-cpi-yoy",
            "bls",
            [
                (date(2024, 6, 1), 300.0),
                (date(2024, 7, 1), 301.0),
                (date(2025, 6, 1), 330.0),
                (date(2025, 7, 1), 333.0),
            ],
        )
        # Japan M2 level -> YoY (two YoY points -> one slope point).
        seed_macro(
            self.conn,
            "japan-m2-yoy",
            "boj",
            [
                (date(2024, 6, 1), 1_200_000.0),
                (date(2024, 7, 1), 1_202_000.0),
                (date(2025, 6, 1), 1_236_000.0),
                (date(2025, 7, 1), 1_240_000.0),
            ],
        )
        # Eurozone inflation + policy (for the real rate).
        seed_macro(self.conn, "eurozone-cpi-yoy", "eurostat", [(date(2025, 6, 1), 2.5)])
        seed_macro(self.conn, "ecb-deposit-rate", "ecb", [(date(2025, 6, 11), 2.0)])

    def tearDown(self):
        self.conn.close()

    def test_policy_rate_trend_from_event_series(self):
        result = derived_kpi("policy_rate_trend", MARKET_JAPAN, conn=self.conn)
        directions = {p.value for p in result.points}
        self.assertIn(TrendDirection.INCREASING, directions)  # the 2024-09 hike
        self.assertIn(TrendDirection.STABLE, directions)  # months without a change

    def test_inflation_rate_trend(self):
        result = derived_kpi("inflation_rate_trend", MARKET_USA, conn=self.conn)
        self.assertTrue(all(p.value is TrendDirection.INCREASING for p in result.points))

    def test_m2_growth_trend(self):
        result = derived_kpi("m2_growth_trend", MARKET_JAPAN, conn=self.conn)
        # Monthly YoY series -> one direction point.
        self.assertEqual(len(result.points), 1)

    def test_real_interest_rate(self):
        result = derived_kpi("real_interest_rate", MARKET_SPAIN_EUROZONE, conn=self.conn)
        self.assertEqual(
            [(p.obs_date, p.value) for p in result.points],
            [(date(2025, 6, 30), -0.5)],
        )

    def test_real_interest_rate_trend(self):
        latest = latest_derived_kpi("real_interest_rate_trend", MARKET_SPAIN_EUROZONE, conn=self.conn)
        # A single real-rate point -> no slope point yet.
        self.assertIsNone(latest)

    def test_undefined_market_raises(self):
        with self.assertRaises(DerivedNotDefined):
            derived_kpi("real_interest_rate", MARKET_USA, conn=self.conn)

    def test_unknown_kpi_raises(self):
        with self.assertRaises(DerivedNotDefined):
            derived_kpi("nope", MARKET_USA, conn=self.conn)


if __name__ == "__main__":
    unittest.main()
