"""Tests for the macro sync service (Phase 1)."""

import sqlite3
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import PropertyMock, patch

from db import queries
from services.config import Config
from services.macro_client import MacroUnavailable, Observation
from services.macro_sync_svc import sync_series

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    # Seed one series (migration seeds the full set; tests need only one+).
    conn.execute(
        "INSERT INTO macro_series (slug, provider, name, unit, source_url, update_frequency) "
        "VALUES ('usa-cpi-yoy', 'bls', 'US CPI', '%', "
        "'https://www.investing.com/economic-calendar/cpi-733', 'monthly')"
    )
    conn.execute(
        "INSERT INTO macro_series (slug, provider, name, unit, source_url, update_frequency) "
        "VALUES ('eurozone-m2-yoy', 'ecb', 'EU M2', '%', "
        "'https://data.ecb.europa.eu/data-detail-api/X', 'monthly')"
    )
    conn.commit()
    return conn


class MacroSyncTestBase(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.db_patcher = patch("services.macro_sync_svc.get_db", return_value=self.conn)
        self.db_patcher.start()
        # Freshness off and pacing off unless a test overrides them.
        self.fresh_patcher = patch.object(
            Config, "macro_sync_freshness_hours", new_callable=PropertyMock, return_value=0
        )
        self.fresh_patcher.start()
        self.pace_patcher = patch.object(Config, "macro_sync_pace_seconds", new_callable=PropertyMock, return_value=0)
        self.pace_patcher.start()
        self.breaker_patcher = patch("services.macro_sync_svc.get_breaker")
        self.breaker = self.breaker_patcher.start()
        self.breaker.return_value.can_proceed.return_value = True

    def tearDown(self):
        self.breaker_patcher.stop()
        self.pace_patcher.stop()
        self.fresh_patcher.stop()
        self.db_patcher.stop()
        self.conn.close()

    def patch_fetch(self, mapping):
        """Patch fetch_series to return observations per provider.

        A mapping value that is an Exception instance is raised instead (to
        simulate a provider failure for that provider).
        """

        def _side_effect(provider, url):
            value = mapping[provider]
            if isinstance(value, Exception):
                raise value
            return value

        return patch("services.macro_sync_svc.fetch_series", side_effect=_side_effect)


class TestSyncSeries(MacroSyncTestBase):
    def test_inserts_observations_and_updates_timestamp(self):
        obs = [Observation(date(2026, 8, 1), 3.2), Observation(date(2026, 7, 1), 3.3)]
        with self.patch_fetch({"bls": obs, "ecb": []}):
            result = sync_series(["usa-cpi-yoy"])

        self.assertTrue(result["synced"])
        self.assertEqual(result["total_added"], 2)
        rows = queries.get_macro_observations(self.conn, "usa-cpi-yoy")
        self.assertEqual([(r["obs_date"], r["value"]) for r in rows], [("2026-07-01", 3.3), ("2026-08-01", 3.2)])
        series = queries.get_macro_series(self.conn, "usa-cpi-yoy")
        assert series is not None
        self.assertIsNotNone(series["last_synced_at"])

    def test_second_sync_is_idempotent(self):
        obs = [Observation(date(2026, 8, 1), 3.2)]
        with self.patch_fetch({"bls": obs, "ecb": []}):
            sync_series(["usa-cpi-yoy"])
            result = sync_series(["usa-cpi-yoy"])
        self.assertEqual(result["total_added"], 0)

    def test_provider_error_isolated_per_series(self):
        with self.patch_fetch({"bls": MacroUnavailable("boom"), "ecb": []}):
            result = sync_series(["usa-cpi-yoy"])
        item = result["series"][0]
        self.assertEqual(item["added"], 0)
        self.assertIn("boom", item["error"])
        # No observations written; failure keeps existing data intact.
        self.assertEqual(queries.get_macro_observations(self.conn, "usa-cpi-yoy"), [])

    def test_freshness_skip(self):
        self.fresh_patcher.stop()
        with patch.object(Config, "macro_sync_freshness_hours", new_callable=PropertyMock, return_value=12):
            recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            self.conn.execute("UPDATE macro_series SET last_synced_at = ? WHERE slug = 'usa-cpi-yoy'", (recent,))
            self.conn.commit()
            with self.patch_fetch({"bls": [Observation(date(2026, 8, 1), 3.2)], "ecb": []}):
                result = sync_series(["usa-cpi-yoy"])
        self.assertEqual(result["series"][0]["skipped"], "fresh")

    def test_provider_dispatch_uses_source_url(self):
        with self.patch_fetch({"bls": [Observation(date(2026, 8, 1), 1.0)], "ecb": []}) as mock_fetch:
            sync_series(["usa-cpi-yoy"])
        provider, url = mock_fetch.call_args[0]
        self.assertEqual(provider, "bls")
        self.assertIn("cpi-733", url)

    def test_single_flight(self):
        import services.macro_sync_svc as svc

        acquired = svc._sync_lock.acquire(blocking=False)
        try:
            self.assertTrue(acquired)
            result = sync_series()
            self.assertTrue(result.get("busy"))
        finally:
            svc._sync_lock.release()

    def test_no_series_returns_empty(self):
        with self.patch_fetch({"bls": [], "ecb": []}):
            result = sync_series(["does-not-exist"])
        self.assertEqual(result["series"], [])

    def test_circuit_open_flag(self):
        self.breaker.return_value.can_proceed.return_value = False
        with self.patch_fetch({"bls": [Observation(date(2026, 8, 1), 1.0)], "ecb": []}):
            result = sync_series(["usa-cpi-yoy"])
        self.assertTrue(result.get("circuit_open"))


if __name__ == "__main__":
    unittest.main()
