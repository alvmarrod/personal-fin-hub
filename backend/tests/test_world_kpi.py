"""Tests for the world-KPI layer (derivations + registry/access)."""

import sqlite3
import unittest
from datetime import date
from pathlib import Path

from services.world_kpi_calc import KpiPoint, apply, yoy_from_level
from services.world_kpi_svc import (
    MARKET_JAPAN,
    MARKET_SPAIN_EUROZONE,
    MARKET_USA,
    KpiNotDefined,
    get_source,
    latest_world_kpi,
    list_world_kpis,
    market_keys,
    world_kpi,
)

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_series(conn, slug, provider, points):
    conn.execute(
        "INSERT INTO macro_series (slug, provider, name) VALUES (?, ?, ?)",
        (slug, provider, slug),
    )
    conn.executemany(
        "INSERT INTO macro_series_observations (slug, obs_date, value) VALUES (?, ?, ?)",
        [(slug, d.isoformat(), v) for d, v in points],
    )
    conn.commit()


class TestNormalizations(unittest.TestCase):
    def test_yoy_from_level(self):
        series = [
            KpiPoint(date(2024, 1, 1), 100.0),
            KpiPoint(date(2024, 2, 1), 110.0),
            KpiPoint(date(2025, 1, 1), 110.0),
            KpiPoint(date(2025, 2, 1), 121.0),
        ]
        yoy = {p.obs_date: p.value for p in yoy_from_level(series)}
        self.assertAlmostEqual(yoy[date(2025, 1, 1)], 10.0, places=6)
        self.assertAlmostEqual(yoy[date(2025, 2, 1)], 10.0, places=6)
        # Points without a 12-month-ago counterpart are dropped.
        self.assertNotIn(date(2024, 1, 1), yoy)

    def test_none_is_passthrough(self):
        series = [KpiPoint(date(2025, 1, 1), 5.0)]
        self.assertEqual(apply("none", series), series)

    def test_unknown_normalization_raises(self):
        with self.assertRaises(KeyError):
            apply("nope", [])


class TestRegistry(unittest.TestCase):
    def test_lists_kpis(self):
        self.assertEqual(list_world_kpis(), ["inflation_rate", "m2_growth", "policy_rate"])

    def test_market_keys(self):
        self.assertEqual(market_keys("m2_growth"), [MARKET_JAPAN, MARKET_SPAIN_EUROZONE, MARKET_USA])

    def test_source_normalization(self):
        self.assertEqual(get_source("m2_growth", MARKET_USA).normalization, "yoy_from_level")
        self.assertEqual(get_source("inflation_rate", MARKET_USA).normalization, "yoy_from_level")
        self.assertEqual(get_source("inflation_rate", MARKET_SPAIN_EUROZONE).normalization, "none")

    def test_undefined_kpi_raises(self):
        with self.assertRaises(KpiNotDefined):
            get_source("yield_curve_slope", MARKET_JAPAN)

    def test_undefined_market_raises(self):
        with self.assertRaises(KpiNotDefined):
            get_source("policy_rate", MARKET_USA)


class TestWorldKpiAccess(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        # USA CPI index (level) for two years -> YoY.
        seed_series(
            self.conn,
            "usa-cpi-yoy",
            "bls",
            [(date(2024, 8, 1), 300.0), (date(2025, 8, 1), 330.0)],
        )
        # USA M2 level -> YoY.
        seed_series(
            self.conn,
            "usa-m2-money-supply",
            "fred",
            [(date(2024, 8, 1), 20000.0), (date(2025, 8, 1), 21000.0)],
        )
        # Japan M2 level -> YoY.
        seed_series(
            self.conn,
            "japan-m2-yoy",
            "boj",
            [(date(2024, 8, 1), 1_200_000.0), (date(2025, 8, 1), 1_236_000.0)],
        )
        # Eurozone CPI is already an annual rate -> passthrough.
        seed_series(self.conn, "eurozone-cpi-yoy", "eurostat", [(date(2025, 12, 1), 2.0)])
        # Eurozone M2 already YoY -> passthrough.
        seed_series(self.conn, "eurozone-m2-yoy", "ecb", [(date(2025, 12, 1), 3.2)])
        # Policy rate (event-based) -> passthrough.
        seed_series(self.conn, "ecb-deposit-rate", "ecb", [(date(2025, 6, 11), 2.0)])

    def tearDown(self):
        self.conn.close()

    def test_usa_cpi_yoy_derived(self):
        latest = latest_world_kpi("inflation_rate", MARKET_USA, conn=self.conn)
        assert latest is not None
        self.assertEqual(latest.obs_date, date(2025, 8, 1))
        self.assertAlmostEqual(latest.value, 10.0, places=6)

    def test_usa_m2_yoy_derived(self):
        latest = latest_world_kpi("m2_growth", MARKET_USA, conn=self.conn)
        assert latest is not None
        self.assertAlmostEqual(latest.value, 5.0, places=6)

    def test_japan_m2_yoy_derived(self):
        latest = latest_world_kpi("m2_growth", MARKET_JAPAN, conn=self.conn)
        assert latest is not None
        self.assertAlmostEqual(latest.value, 3.0, places=6)

    def test_eurozone_cpi_passthrough(self):
        series = world_kpi("inflation_rate", MARKET_SPAIN_EUROZONE, conn=self.conn)
        self.assertEqual(series, [KpiPoint(date(2025, 12, 1), 2.0)])

    def test_policy_rate_passthrough(self):
        series = world_kpi("policy_rate", MARKET_SPAIN_EUROZONE, conn=self.conn)
        self.assertEqual(series, [KpiPoint(date(2025, 6, 11), 2.0)])

    def test_empty_series_latest_none(self):
        seed_series(self.conn, "boj-policy-rate", "boj", [])
        self.assertIsNone(latest_world_kpi("policy_rate", MARKET_JAPAN, conn=self.conn))

    def test_undefined_access_raises(self):
        with self.assertRaises(KpiNotDefined):
            world_kpi("inflation_rate", MARKET_JAPAN, conn=self.conn)


if __name__ == "__main__":
    unittest.main()
