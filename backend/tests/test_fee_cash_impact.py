"""Phase 5 tests: fee/tax cash-impact engine, balance walks, reconciliation hooks."""

import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from db import queries
from models import (
    TransactionCreate,
    TransactionFeeCreate,
    TransactionTaxCreate,
)
from models.enums import EntityType, FeeNature, FeeType, TransactionType

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_entity(conn: sqlite3.Connection, main_currency: str | None = None) -> int:
    return queries.create_entity(
        conn,
        "Test Broker",
        EntityType.BROKER,
        main_currency=main_currency,
    )


def seed_currencies(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "USD", "USD", 1.0, datetime(2024, 1, 1))
    queries.insert_rate(conn, "EUR", "USD", 1.10, datetime(2024, 1, 1))
    queries.insert_rate(conn, "JPY", "USD", 0.0067, datetime(2024, 1, 1))
    queries.insert_rate(conn, "USD", "JPY", 149.0, datetime(2024, 1, 1))
    queries.insert_rate(conn, "EUR", "JPY", 164.0, datetime(2024, 1, 1))


# ---------------------------------------------------------------------------
# Fee cash-impact engine
# ---------------------------------------------------------------------------


class TestFeeCashImpactEngine(unittest.TestCase):
    """compute_fee_cash_out_at: nature math + currency conversion + exclusions."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn, main_currency="JPY")
        seed_currencies(self.conn)

    def tearDown(self):
        self.conn.close()

    def _create_buy(self, ts, value, currency="EUR"):
        return queries.create_transaction(
            self.conn,
            ts,
            TransactionType.INVESTMENT_BUY.value,
            self.eid,
            currency,
            value,
        )

    def _add_fee(self, tx_id, nature, fixed=0.0, pct=0.0, currency="EUR"):
        queries.create_fee(
            self.conn,
            tx_id,
            FeeType.BROKER.value,
            nature.value,
            currency,
            fixed,
            pct,
        )

    def _add_tax(self, tx_id, amount, currency="EUR"):
        queries.create_tax(
            self.conn,
            tx_id,
            "capital_gains",
            amount,
            currency,
        )

    def test_fixed_fee_converted_to_main_currency(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 50000.0, "EUR")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=552.54, currency="JPY")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total, 552.54, places=2)

    def test_percentage_fee_converted_to_main_currency(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 10000.0, "EUR")
        self._add_fee(tx_id, FeeNature.PERCENTAGE, pct=0.5, currency="EUR")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        fee_eur = 10000.0 * 0.5 / 100.0
        self.assertAlmostEqual(total, fee_eur * 164.0, places=2)

    def test_both_nature(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 10000.0, "EUR")
        self._add_fee(tx_id, FeeNature.BOTH, fixed=10.0, pct=0.1, currency="EUR")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        fee_eur = 10.0 + 10000.0 * 0.1 / 100.0
        self.assertAlmostEqual(total, fee_eur * 164.0, places=2)

    def test_min_nature(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 10000.0, "EUR")
        self._add_fee(tx_id, FeeNature.MIN, fixed=5.0, pct=0.5, currency="EUR")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        fee_eur = min(5.0, 10000.0 * 0.5 / 100.0)
        self.assertAlmostEqual(total, fee_eur * 164.0, places=2)

    def test_same_currency_no_conversion(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 50000.0, "JPY")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=500.0, currency="JPY")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total, 500.0, places=2)

    def test_non_main_currency_returns_zero(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 5000.0, "USD")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=10.0, currency="USD")
        total_eur = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "EUR",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total_eur, 0.0, places=2)

    def test_null_main_currency_returns_zero(self):
        conn = in_memory_db()
        eid = seed_entity(conn, main_currency=None)
        seed_currencies(conn)
        tx_id = queries.create_transaction(
            conn,
            "2024-06-01T10:00:00",
            TransactionType.INVESTMENT_BUY.value,
            eid,
            "EUR",
            5000.0,
        )
        queries.create_fee(
            conn,
            tx_id,
            FeeType.BROKER.value,
            FeeNature.FIXED.value,
            "EUR",
            50.0,
            0.0,
        )
        total = queries.compute_fee_cash_out_at(
            conn,
            eid,
            "EUR",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total, 0.0, places=2)
        conn.close()

    def test_tax_amount_included(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 50000.0, "EUR")
        self._add_tax(tx_id, 1000.0, "EUR")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total, 1000.0 * 164.0, places=2)

    def test_exclude_transaction_id(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 50000.0, "EUR")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=500.0, currency="JPY")
        total_included = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        self.assertGreater(total_included, 0.0)
        total_excluded = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
            exclude_transaction_id=tx_id,
        )
        self.assertAlmostEqual(total_excluded, 0.0, places=2)

    def test_multiple_fees_summed(self):
        tx_id = self._create_buy("2024-06-01T10:00:00", 50000.0, "EUR")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=100.0, currency="JPY")
        self._add_fee(tx_id, FeeNature.FIXED, fixed=200.0, currency="JPY")
        self._add_tax(tx_id, 50.0, "JPY")
        total = queries.compute_fee_cash_out_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-01T23:59:59",
        )
        self.assertAlmostEqual(total, 350.0, places=2)


# ---------------------------------------------------------------------------
# Balance walks with fees
# ---------------------------------------------------------------------------


class TestBalanceWalksWithFees(unittest.TestCase):
    """get_balance_at_date includes the fee term when querying the main currency."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn, main_currency="JPY")
        seed_currencies(self.conn)

    def tearDown(self):
        self.conn.close()

    def _add_fee(self, tx_id, nature, fixed=0.0, pct=0.0, currency="JPY"):
        queries.create_fee(
            self.conn,
            tx_id,
            FeeType.BROKER.value,
            nature.value,
            currency,
            fixed,
            pct,
        )

    def test_snapshot_path_subtracts_post_snapshot_fees(self):
        """Fees deducted from the main-currency (JPY) balance after snapshot."""
        TT = TransactionType
        queries.create_transaction(
            self.conn,
            "2024-05-01T10:00:00",
            TT.INCOME.value,
            self.eid,
            "JPY",
            1_000_000.0,
            income_category="salary",
        )
        queries.create_balance_snapshot(
            self.conn,
            self.eid,
            "JPY",
            1_000_000.0,
            "2024-06-01T00:00:00",
        )
        tx_id = queries.create_transaction(
            self.conn,
            "2024-06-15T10:00:00",
            TT.INVESTMENT_BUY.value,
            self.eid,
            "EUR",
            10_000.0,
        )
        self._add_fee(tx_id, FeeNature.FIXED, fixed=164_000.0, currency="JPY")
        balance = queries.get_balance_at_date(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-15T23:59:59",
        )
        # snapshot=1M, no post-snapshot JPY txns, fee=164000
        self.assertAlmostEqual(balance, 1_000_000.0 - 164_000.0, places=2)

    def test_sql_path_subtracts_all_fees(self):
        """Fees deducted from main-currency balance (no snapshot path)."""
        TT = TransactionType
        queries.create_transaction(
            self.conn,
            "2024-06-01T10:00:00",
            TT.INCOME.value,
            self.eid,
            "JPY",
            1_000_000.0,
            income_category="salary",
        )
        tx_id = queries.create_transaction(
            self.conn,
            "2024-06-15T10:00:00",
            TT.INVESTMENT_BUY.value,
            self.eid,
            "EUR",
            10_000.0,
        )
        self._add_fee(tx_id, FeeNature.FIXED, fixed=164_000.0, currency="JPY")
        balance = queries.get_balance_at_date(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-15T23:59:59",
        )
        self.assertAlmostEqual(balance, 1_000_000.0 - 164_000.0, places=2)

    def test_non_main_currency_not_affected_by_fees(self):
        """EUR balance is not affected by fees (fees charge main JPY pocket)."""
        TT = TransactionType
        queries.create_transaction(
            self.conn,
            "2024-06-01T10:00:00",
            TT.INCOME.value,
            self.eid,
            "EUR",
            50_000.0,
            income_category="salary",
        )
        tx_id = queries.create_transaction(
            self.conn,
            "2024-06-15T10:00:00",
            TT.INVESTMENT_BUY.value,
            self.eid,
            "EUR",
            10_000.0,
        )
        self._add_fee(tx_id, FeeNature.FIXED, fixed=164_000.0, currency="JPY")
        balance = queries.get_balance_at_date(
            self.conn,
            self.eid,
            "EUR",
            "2024-06-15T23:59:59",
        )
        # Fee is in JPY → main pocket → EUR unaffected
        self.assertAlmostEqual(balance, 50_000.0 - 10_000.0, places=2)

    def test_fee_exclusion_on_edit(self):
        """Excluding a transaction also excludes its fees from the main-currency balance."""
        TT = TransactionType
        queries.create_transaction(
            self.conn,
            "2024-06-01T10:00:00",
            TT.INCOME.value,
            self.eid,
            "JPY",
            1_000_000.0,
            income_category="salary",
        )
        tx_id = queries.create_transaction(
            self.conn,
            "2024-06-15T10:00:00",
            TT.INVESTMENT_BUY.value,
            self.eid,
            "EUR",
            10_000.0,
        )
        self._add_fee(tx_id, FeeNature.FIXED, fixed=164_000.0, currency="JPY")
        # Without exclusion: 1M - 164K = 836K
        balance_full = queries.get_balance_at_date(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-15T23:59:59",
        )
        self.assertAlmostEqual(balance_full, 1_000_000.0 - 164_000.0, places=2)
        # With exclusion: fee gone → 1M
        balance_excl = queries.get_balance_at_date(
            self.conn,
            self.eid,
            "JPY",
            "2024-06-15T23:59:59",
            exclude_transaction_id=tx_id,
        )
        self.assertAlmostEqual(balance_excl, 1_000_000.0, places=2)


# ---------------------------------------------------------------------------
# Reconciliation hooks
# ---------------------------------------------------------------------------


class TestFeeReconciliationHooks(unittest.TestCase):
    """Fee/tax CRUD triggers snapshot adjustment refresh on the main-currency pair."""

    def setUp(self):
        self.conn = in_memory_db()
        # main_currency = "EUR" so EUR balance includes fees
        self.eid = seed_entity(self.conn, main_currency="EUR")
        seed_currencies(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.patcher2 = patch("services.transaction_fee_svc.get_db", return_value=self.conn)
        self.patcher2.start()
        self.patcher3 = patch("services.transaction_tax_svc.get_db", return_value=self.conn)
        self.patcher3.start()
        self.patcher4 = patch("services.balance_snapshot_svc.get_db", return_value=self.conn)
        self.patcher4.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()
        self.conn.close()

    def _import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def _import_fee_svc(self):
        from services import transaction_fee_svc

        return transaction_fee_svc

    def _import_tax_svc(self):
        from services import transaction_tax_svc

        return transaction_tax_svc

    def _import_snap_svc(self):
        from services import balance_snapshot_svc

        return balance_snapshot_svc

    def _create_snapshot(self, currency, amount, ts):
        svc = self._import_snap_svc()
        return svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency=currency,
                amount=amount,
                timestamp=datetime.fromisoformat(ts),
            )
        )

    def test_adding_fee_refreshes_snapshot_adjustment(self):
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        snap = self._create_snapshot("EUR", 50_000.0, "2024-07-01T00:00:00")
        adj_before = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_before is not None

        fee_svc = self._import_fee_svc()
        fee_svc.create(
            TransactionFeeCreate(
                transaction_id=tx.id,
                fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED,
                fixed_amount=100.0,
                percentage=0.0,
                currency="EUR",
            )
        )
        adj_after = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_after is not None
        # Fee=100 drains main pocket → adjustment must absorb +100
        self.assertAlmostEqual(
            adj_after["total_value"],
            adj_before["total_value"] + 100.0,
            places=2,
        )

    def test_deleting_fee_restores_snapshot_adjustment(self):
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        snap = self._create_snapshot("EUR", 50_000.0, "2024-07-01T00:00:00")
        adj_before = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_before is not None

        fee_svc = self._import_fee_svc()
        fee_resp = fee_svc.create(
            TransactionFeeCreate(
                transaction_id=tx.id,
                fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED,
                fixed_amount=100.0,
                percentage=0.0,
                currency="EUR",
            )
        )
        fee_svc.delete(fee_resp.id)
        adj_after = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_after is not None
        self.assertAlmostEqual(
            adj_after["total_value"],
            adj_before["total_value"],
            places=2,
        )

    def test_standalone_tax_reconciles(self):
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        snap = self._create_snapshot("EUR", 50_000.0, "2024-07-01T00:00:00")
        adj_before = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_before is not None

        tax_svc = self._import_tax_svc()
        tax_svc.create(
            TransactionTaxCreate(
                transaction_id=tx.id,
                tax_type="capital_gains",
                tax_amount=200.0,
                currency="EUR",
            )
        )
        adj_after = queries.get_adjustment_transaction(
            self.conn,
            self.eid,
            "EUR",
            snap.id,
        )
        assert adj_after is not None
        self.assertAlmostEqual(
            adj_after["total_value"],
            adj_before["total_value"] + 200.0,
            places=2,
        )


# ---------------------------------------------------------------------------
# Main-pocket inference lifecycle
# ---------------------------------------------------------------------------


class TestMainPocketInference(unittest.TestCase):
    """Fee-driven injections on the main pocket."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn, main_currency="JPY")
        seed_currencies(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.patcher2 = patch("services.transaction_fee_svc.get_db", return_value=self.conn)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        self.conn.close()

    def _import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def _import_fee_svc(self):
        from services import transaction_fee_svc

        return transaction_fee_svc

    def test_fee_creates_main_pocket_injection(self):
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        fee_svc = self._import_fee_svc()
        fee_svc.create(
            TransactionFeeCreate(
                transaction_id=tx.id,
                fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED,
                fixed_amount=500_000.0,
                percentage=0.0,
                currency="JPY",
            )
        )
        adj = queries.get_injected_adjustment_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-05-31T23:59:59",
        )
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 500_000.0, places=2)

    def test_fee_does_not_inject_when_anchored(self):
        queries.create_balance_snapshot(
            self.conn,
            self.eid,
            "JPY",
            1_000_000.0,
            "2024-01-01T00:00:00",
        )
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        fee_svc = self._import_fee_svc()
        fee_svc.create(
            TransactionFeeCreate(
                transaction_id=tx.id,
                fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED,
                fixed_amount=500_000.0,
                percentage=0.0,
                currency="JPY",
            )
        )
        adj = queries.get_injected_adjustment_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-05-31T23:59:59",
        )
        self.assertIsNone(adj)

    def test_deleting_fee_removes_injection(self):
        svc = self._import_svc()
        tx = svc.create(
            TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
                quantity=10.0,
                unit_price=5000.0,
            )
        )
        fee_svc = self._import_fee_svc()
        fee_resp = fee_svc.create(
            TransactionFeeCreate(
                transaction_id=tx.id,
                fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED,
                fixed_amount=500_000.0,
                percentage=0.0,
                currency="JPY",
            )
        )
        adj = queries.get_injected_adjustment_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-05-31T23:59:59",
        )
        self.assertIsNotNone(adj)
        fee_svc.delete(fee_resp.id)
        adj_after = queries.get_injected_adjustment_at(
            self.conn,
            self.eid,
            "JPY",
            "2024-05-31T23:59:59",
        )
        self.assertIsNone(adj_after)


# ---------------------------------------------------------------------------
# Migration 018
# ---------------------------------------------------------------------------


class TestMigration018(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_entities_table_has_main_currency(self):
        cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(entities)").fetchall()]
        self.assertIn("main_currency", cols)

    def test_create_entity_with_main_currency(self):
        eid = queries.create_entity(
            self.conn,
            "IBKR",
            EntityType.BROKER,
            main_currency="JPY",
        )
        row = queries.get_entity(self.conn, eid)
        assert row is not None
        self.assertEqual(row["main_currency"], "JPY")

    def test_create_entity_null_main_currency(self):
        eid = queries.create_entity(self.conn, "Bank", EntityType.BANK)
        row = queries.get_entity(self.conn, eid)
        assert row is not None
        self.assertIsNone(row["main_currency"])


if __name__ == "__main__":
    unittest.main()
