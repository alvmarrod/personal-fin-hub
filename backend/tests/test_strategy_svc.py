import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from db.connection import ProfileScopedConnection
from models import HistoricalAssetClassPoint, HoldingByEntityLine, StrategySetBody
from models.enums import AssetClass
from services import strategy_svc

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

TARGETS: dict[str, float] = {"equities": 55.0, "bonds": 30.0, "cash": 15.0, "real_estate": 0.0, "gold": 0.0}


class StrategyServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA_PATH.read_text())
        conn.execute("INSERT INTO profiles (id, name, timezone) VALUES (1, 'Default', 'UTC')")
        conn.commit()
        conn.close()

        self.profile_id = 1
        self.patcher = patch("services.strategy_svc.get_db", side_effect=self._connect)
        self.patcher.start()
        self.analytics_patcher = patch("services.strategy_svc.analytics_svc.get_holdings_by_entity", return_value=[])
        self.analytics_patcher.start()

    def tearDown(self):
        self.analytics_patcher.stop()
        self.patcher.stop()
        self.tmp.cleanup()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, factory=ProfileScopedConnection)
        conn.row_factory = sqlite3.Row
        conn.profile_id = self.profile_id
        return conn

    def _body(self, effective_from: str, **overrides) -> StrategySetBody:
        targets = dict(TARGETS)
        targets.update(overrides)
        return StrategySetBody(effective_from=date.fromisoformat(effective_from), targets=targets)

    def _holdings(self, *lines) -> None:
        self.analytics_patcher.stop()
        self.analytics_patcher = patch(
            "services.strategy_svc.analytics_svc.get_holdings_by_entity",
            return_value=[
                HoldingByEntityLine(asset_class=asset_class, current_value=value, currency="EUR", rate_missing=missing)
                for asset_class, value, missing in lines
            ],
        )
        self.analytics_patcher.start()

    def test_mapping_covers_every_known_class(self):
        for asset_class in AssetClass:
            self.assertIn(asset_class.value, strategy_svc.BUCKET_OF_CLASS)
        self.assertEqual(strategy_svc.BUCKET_OF_CLASS["CASH"], "cash")

    def test_create_and_list_sets(self):
        strategy_svc.create(self._body("2026-01-01", equities=60, bonds=25, cash=15))
        strategy_svc.create(self._body("2027-01-01"))

        sets = strategy_svc.list_sets()

        self.assertEqual([s.effective_from for s in sets], [date(2026, 1, 1), date(2027, 1, 1)])
        self.assertEqual(sets[0].targets["equities"], 60)
        self.assertEqual(set(sets[0].targets), set(strategy_svc.BUCKETS))
        self.assertTrue(sets[0].updated_at)

    def test_create_rejects_a_duplicate_date(self):
        strategy_svc.create(self._body("2026-01-01"))
        with self.assertRaises(strategy_svc.StrategyExists):
            strategy_svc.create(self._body("2026-01-01"))

    def test_replace_updates_a_set(self):
        strategy_svc.create(self._body("2026-01-01"))
        updated = strategy_svc.replace(date(2026, 1, 1), self._body("2026-01-01", equities=70, bonds=20, cash=10))

        self.assertEqual(updated.targets["equities"], 70)
        self.assertEqual(strategy_svc.list_sets()[0].targets["bonds"], 20)

    def test_replace_missing_set(self):
        with self.assertRaises(strategy_svc.StrategyNotFound):
            strategy_svc.replace(date(2026, 1, 1), self._body("2026-01-01"))

    def test_delete_set(self):
        strategy_svc.create(self._body("2026-01-01"))
        strategy_svc.delete(date(2026, 1, 1))
        self.assertEqual(strategy_svc.list_sets(), [])

    def test_delete_missing_set(self):
        with self.assertRaises(strategy_svc.StrategyNotFound):
            strategy_svc.delete(date(2026, 1, 1))

    def test_drift_without_an_effective_set(self):
        strategy_svc.create(self._body("2027-01-01"))

        result = strategy_svc.drift("EUR", today=date(2026, 6, 1))

        self.assertIsNone(result.effective_from)
        self.assertEqual(result.buckets, [])
        self.assertEqual(result.total, 0.0)

    def test_drift_resolves_the_latest_past_set(self):
        strategy_svc.create(self._body("2026-01-01"))
        self._holdings(
            ("VI", 5500.0, False),
            ("FI", 3000.0, False),
            ("CASH", 1000.0, False),
            (None, 500.0, False),
        )

        result = strategy_svc.drift("EUR", today=date(2026, 6, 1))

        self.assertEqual(result.effective_from, date(2026, 1, 1))
        self.assertEqual(result.total, 10000.0)
        equities = next(b for b in result.buckets if b.bucket == "equities")
        self.assertEqual(equities.target_pct, 55)
        self.assertEqual(equities.value, 5500.0)
        self.assertEqual(equities.share_pct, 55.0)
        self.assertEqual(equities.drift_pp, 0.0)
        self.assertEqual(equities.amount_to_move, 0.0)
        self.assertEqual(result.unassigned.value, 500.0)
        self.assertEqual(result.unassigned.share_pct, 5.0)

    def test_drift_uses_the_next_set_after_its_date(self):
        strategy_svc.create(self._body("2026-01-01"))
        strategy_svc.create(self._body("2027-01-01", equities=60, bonds=25, cash=15))
        self._holdings(("VI", 5500.0, False), ("FI", 3000.0, False), ("CASH", 1500.0, False))

        result = strategy_svc.drift("EUR", today=date(2027, 6, 1))

        self.assertEqual(result.effective_from, date(2027, 1, 1))
        equities = next(b for b in result.buckets if b.bucket == "equities")
        self.assertEqual(equities.target_pct, 60)
        self.assertEqual(equities.share_pct, 55.0)
        self.assertEqual(equities.drift_pp, -5.0)
        self.assertEqual(equities.amount_to_move, 500.0)

    def test_drift_flags_missing_rates_per_bucket(self):
        strategy_svc.create(self._body("2026-01-01"))
        self._holdings(("VI", 1000.0, True), ("FI", 1000.0, False))

        result = strategy_svc.drift("EUR", today=date(2026, 6, 1))

        equities = next(b for b in result.buckets if b.bucket == "equities")
        bonds = next(b for b in result.buckets if b.bucket == "bonds")
        self.assertTrue(equities.rate_missing)
        self.assertFalse(bonds.rate_missing)
        self.assertTrue(result.rate_missing)

    def test_drift_groups_fixed_income_subtypes(self):
        strategy_svc.create(self._body("2026-01-01"))
        self._holdings(("FI", 100.0, False), ("corp FI", 100.0, False), ("Sovereign FI", 100.0, False))

        result = strategy_svc.drift("EUR", today=date(2026, 6, 1))

        bonds = next(b for b in result.buckets if b.bucket == "bonds")
        self.assertEqual(bonds.value, 300.0)

    def _historical(self, *points) -> None:
        self.history_patcher = patch(
            "services.strategy_svc.analytics_svc.get_historical_values_by_asset_class",
            return_value=[
                HistoricalAssetClassPoint(date=day, asset_class=asset_class, value=value)
                for day, asset_class, value in points
            ],
        )
        self.history_patcher.start()
        self.addCleanup(self.history_patcher.stop)

    def test_history_maps_classes_to_buckets_and_targets(self):
        strategy_svc.create(self._body("2026-01-01"))
        strategy_svc.create(self._body("2027-01-01", equities=60, bonds=25, cash=15))
        self._historical(
            ("2026-06-01", "VI", 550.0),
            ("2026-06-01", "FI", 300.0),
            ("2026-06-01", "CASH", 150.0),
            ("2026-06-01", "UNSPECIFIED", 100.0),
            ("2027-06-01", "VI", 600.0),
            ("2027-06-01", "FI", 250.0),
            ("2027-06-01", "CASH", 150.0),
        )

        result = strategy_svc.history("2026-01-01", "2027-12-31", "month", "EUR")

        equities = [p for p in result.points if p.bucket == "equities"]
        self.assertEqual([p.date for p in equities], ["2026-06-01", "2027-06-01"])
        self.assertEqual(equities[0].share_pct, 50.0)
        self.assertEqual(equities[0].target_pct, 55.0)
        self.assertEqual(equities[1].share_pct, 60.0)
        self.assertEqual(equities[1].target_pct, 60.0)

        unassigned = [p for p in result.points if p.bucket == "unassigned"]
        self.assertEqual(len(unassigned), 1)
        self.assertEqual(unassigned[0].value, 100.0)
        self.assertIsNone(unassigned[0].target_pct)

        first_date = [p for p in result.points if p.date == "2026-06-01"]
        self.assertEqual(len(first_date), 6)  # five buckets + unassigned

    def test_history_has_no_target_before_the_first_set(self):
        strategy_svc.create(self._body("2027-01-01"))
        self._historical(("2026-06-01", "VI", 100.0))

        result = strategy_svc.history("2026-01-01", "2026-12-31", "month", "EUR")

        self.assertTrue(all(p.target_pct is None for p in result.points))

    def test_history_forwards_the_interval(self):
        strategy_svc.create(self._body("2026-01-01"))
        with patch(
            "services.strategy_svc.analytics_svc.get_historical_values_by_asset_class", return_value=[]
        ) as historical:
            strategy_svc.history("2026-01-01", "2026-12-31", "week", "EUR")

        historical.assert_called_once_with("2026-01-01", "2026-12-31", "week", None, "EUR")

    def test_sets_are_profile_scoped(self):
        strategy_svc.create(self._body("2026-01-01"))
        self.profile_id = 2

        self.assertEqual(strategy_svc.list_sets(), [])


class StrategyBodyTest(unittest.TestCase):
    def test_requires_all_buckets(self):
        with self.assertRaises(ValueError):
            StrategySetBody(effective_from=date(2026, 1, 1), targets={"equities": 100})

    def test_rejects_a_bad_sum(self):
        with self.assertRaises(ValueError):
            StrategySetBody(
                effective_from=date(2026, 1, 1),
                targets={"equities": 50, "bonds": 30, "cash": 10, "real_estate": 0, "gold": 0},
            )

    def test_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            StrategySetBody(
                effective_from=date(2026, 1, 1),
                targets={"equities": 120, "bonds": -20, "cash": 0, "real_estate": 0, "gold": 0},
            )

    def test_accepts_a_complete_set(self):
        body = StrategySetBody(effective_from=date(2026, 1, 1), targets=TARGETS)
        self.assertEqual(body.targets["equities"], 55.0)


if __name__ == "__main__":
    unittest.main()
