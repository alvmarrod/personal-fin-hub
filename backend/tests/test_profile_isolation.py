import sqlite3
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from typing import cast

from db import analytics_queries, queries
from db.connection import ProfileScopedConnection, get_db, reset_active_profile, set_active_profile
from models.enums import EntityType

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def make_conn(profile_id: int | None = None, name: str | None = None) -> sqlite3.Connection:
    name = name or f"isolation_{uuid.uuid4().hex}"
    conn = sqlite3.connect(
        f"file:{name}?mode=memory&cache=shared",
        uri=True,
        factory=ProfileScopedConnection,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.profile_id = profile_id
    return conn


class IsolationBase(unittest.TestCase):
    """Query-level profile isolation across the 10 ownership tables.

    Uses two in-memory connections scoped to different profiles so every
    ownership query can be checked for row stamping and cross-profile
    invisibility without going through the API layer.
    """

    def setUp(self):
        self.db_name = f"isolation_{uuid.uuid4().hex}"
        self.global_conn = make_conn(name=self.db_name)
        self.global_conn.executescript(SCHEMA_PATH.read_text())
        self.profile_a = queries.create_profile(self.global_conn, "Alpha", None)
        self.profile_b = queries.create_profile(self.global_conn, "Beta", None)
        self.global_conn.commit()
        self.conn_a = make_conn(self.profile_a, name=self.db_name)
        self.conn_b = make_conn(self.profile_b, name=self.db_name)

    def tearDown(self):
        self.global_conn.close()
        self.conn_a.close()
        self.conn_b.close()

    def _seed_shared(self):
        queries.create_self_rate(self.global_conn, "USD", datetime(2026, 1, 1))
        queries.create_market_asset(self.global_conn, "TEST", "USD", "STOCK")
        self.global_conn.commit()

    def _entity_a(self):
        return queries.create_entity(self.conn_a, "Broker A", EntityType.BROKER)

    def _portfolio_asset_a(self):
        return queries.create_portfolio_asset(self.conn_a, market_code="TEST")

    def _transaction_a(self, entity_id=None, portfolio_asset_id=None):
        return queries.create_transaction(
            self.conn_a,
            timestamp="2026-01-01T00:00:00",
            type_="MONEY_IN",
            entity_id=entity_id if entity_id is not None else self._entity_a(),
            currency="USD",
            total_value=100.0,
            portfolio_asset_id=portfolio_asset_id,
        )


class TestEntitiesIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        eid = self._entity_a()
        row = self.global_conn.execute("SELECT profile_id FROM entities WHERE id = ?", (eid,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        self._entity_a()
        self.assertEqual(queries.get_all_entities(self.conn_b), [])
        self.assertEqual(len(queries.get_all_entities(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        eid = self._entity_a()
        self.assertIsNone(queries.get_entity(self.conn_b, eid))
        self.assertIsNotNone(queries.get_entity(self.conn_a, eid))

    def test_update_cross_profile_is_noop(self):
        self._seed_shared()
        eid = self._entity_a()
        self.assertFalse(queries.update_entity(self.conn_b, eid, "Renamed", EntityType.BROKER))
        row = self.global_conn.execute("SELECT name FROM entities WHERE id = ?", (eid,)).fetchone()
        self.assertEqual(row["name"], "Broker A")

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        eid = self._entity_a()
        self.assertFalse(queries.delete_entity(self.conn_b, eid))
        self.assertIsNotNone(queries.get_entity(self.conn_a, eid))

    def test_entity_exists_is_scoped(self):
        self._seed_shared()
        self._entity_a()
        self.assertFalse(queries.entity_exists(self.conn_b, "Broker A", EntityType.BROKER))
        self.assertTrue(queries.entity_exists(self.conn_a, "Broker A", EntityType.BROKER))


class TestFiscalExemptionsIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        fe_id = queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        row = self.global_conn.execute("SELECT profile_id FROM fiscal_exemptions WHERE id = ?", (fe_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        self.assertEqual(queries.get_all_fiscal_exemptions(self.conn_b), [])
        self.assertEqual(len(queries.get_all_fiscal_exemptions(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        fe_id = queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        self.assertIsNone(queries.get_fiscal_exemption(self.conn_b, fe_id))
        self.assertIsNotNone(queries.get_fiscal_exemption(self.conn_a, fe_id))

    def test_update_cross_profile_is_noop(self):
        self._seed_shared()
        fe_id = queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        self.assertFalse(queries.update_fiscal_exemption(self.conn_b, fe_id, exemption_type="CHANGED"))
        row = self.global_conn.execute("SELECT exemption_type FROM fiscal_exemptions WHERE id = ?", (fe_id,)).fetchone()
        self.assertEqual(row["exemption_type"], "NONE_TAX")

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        fe_id = queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        self.assertFalse(queries.delete_fiscal_exemption(self.conn_b, fe_id))
        self.assertIsNotNone(queries.get_fiscal_exemption(self.conn_a, fe_id))


class TestPortfolioAssetsIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        row = self.global_conn.execute("SELECT profile_id FROM portfolio_assets WHERE id = ?", (pa_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        self._portfolio_asset_a()
        self.assertEqual(queries.get_all_portfolio_assets(self.conn_b), [])
        self.assertEqual(len(queries.get_all_portfolio_assets(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        self.assertIsNone(queries.get_portfolio_asset(self.conn_b, pa_id))
        self.assertIsNotNone(queries.get_portfolio_asset(self.conn_a, pa_id))


class TestTransactionsIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        row = self.global_conn.execute("SELECT profile_id FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        self._transaction_a()
        self.assertEqual(queries.get_all_transactions(self.conn_b), [])
        self.assertEqual(len(queries.get_all_transactions(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        self.assertIsNone(queries.get_transaction(self.conn_b, tx_id))
        self.assertIsNotNone(queries.get_transaction(self.conn_a, tx_id))

    def test_get_by_entity_is_scoped(self):
        self._seed_shared()
        eid = self._entity_a()
        self._transaction_a(entity_id=eid)
        self.assertEqual(queries.get_transactions_by_entity(self.conn_b, eid), [])
        self.assertEqual(len(queries.get_transactions_by_entity(self.conn_a, eid)), 1)

    def test_get_by_portfolio_is_scoped(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        self._transaction_a(portfolio_asset_id=pa_id)
        self.assertEqual(queries.get_transactions_by_portfolio(self.conn_b, pa_id), [])
        self.assertEqual(len(queries.get_transactions_by_portfolio(self.conn_a, pa_id)), 1)

    def test_update_cross_profile_is_noop(self):
        self._seed_shared()
        eid = self._entity_a()
        tx_id = self._transaction_a(entity_id=eid)
        self.assertFalse(queries.update_transaction(self.conn_b, tx_id, "2026-01-01T00:00:00", "MONEY_OUT", eid, "USD"))
        row = self.global_conn.execute("SELECT type FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        self.assertEqual(row["type"], "MONEY_IN")

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        self.assertFalse(queries.delete_transaction(self.conn_b, tx_id))
        self.assertIsNotNone(queries.get_transaction(self.conn_a, tx_id))


class TestFeesIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        fee_id = queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "USD", fixed_amount=5.0)
        row = self.global_conn.execute("SELECT profile_id FROM transaction_fees WHERE id = ?", (fee_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "USD")
        self.assertEqual(queries.get_all_fees(self.conn_b), [])
        self.assertEqual(len(queries.get_all_fees(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        fee_id = queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "USD")
        self.assertIsNone(queries.get_fee(self.conn_b, fee_id))
        self.assertIsNotNone(queries.get_fee(self.conn_a, fee_id))

    def test_get_by_transaction_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "USD")
        self.assertEqual(queries.get_fees_by_transaction(self.conn_b, tx_id), [])
        self.assertEqual(len(queries.get_fees_by_transaction(self.conn_a, tx_id)), 1)

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        fee_id = queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "USD")
        queries.delete_fees_by_transaction(self.conn_b, tx_id)
        self.assertIsNotNone(queries.get_fee(self.conn_a, fee_id))


class TestTaxesIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        tax_id = queries.create_tax(self.conn_a, tx_id, "RETENTION", 20.0, "USD", tax_rate=20.0)
        row = self.global_conn.execute("SELECT profile_id FROM transaction_taxes WHERE id = ?", (tax_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        queries.create_tax(self.conn_a, tx_id, "RETENTION", 20.0, "USD")
        self.assertEqual(queries.get_all_taxes(self.conn_b), [])
        self.assertEqual(len(queries.get_all_taxes(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        tax_id = queries.create_tax(self.conn_a, tx_id, "RETENTION", 20.0, "USD")
        self.assertIsNone(queries.get_tax(self.conn_b, tax_id))
        self.assertIsNotNone(queries.get_tax(self.conn_a, tax_id))

    def test_get_by_transaction_is_scoped(self):
        self._seed_shared()
        tx_id = self._transaction_a()
        queries.create_tax(self.conn_a, tx_id, "RETENTION", 20.0, "USD")
        self.assertEqual(queries.get_taxes_by_transaction(self.conn_b, tx_id), [])
        self.assertEqual(len(queries.get_taxes_by_transaction(self.conn_a, tx_id)), 1)


class TestBalanceSnapshotsIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        eid = self._entity_a()
        snap_id = queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        row = self.global_conn.execute("SELECT profile_id FROM balance_snapshots WHERE id = ?", (snap_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        eid = self._entity_a()
        queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        self.assertEqual(queries.get_all_balance_snapshots(self.conn_b), [])
        self.assertEqual(len(queries.get_all_balance_snapshots(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        eid = self._entity_a()
        snap_id = queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        self.assertIsNone(queries.get_balance_snapshot(self.conn_b, snap_id))
        self.assertIsNotNone(queries.get_balance_snapshot(self.conn_a, snap_id))

    def test_get_latest_and_by_entity_are_scoped(self):
        self._seed_shared()
        eid = self._entity_a()
        queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        self.assertIsNone(queries.get_latest_snapshot(self.conn_b, eid, "USD"))
        self.assertEqual(queries.get_snapshots_for_entity(self.conn_b, eid, "USD"), [])
        self.assertIsNotNone(queries.get_latest_snapshot(self.conn_a, eid, "USD"))

    def test_update_cross_profile_is_noop(self):
        self._seed_shared()
        eid = self._entity_a()
        snap_id = queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        self.assertFalse(queries.update_balance_snapshot(self.conn_b, snap_id, eid, "USD", 5.0, "2026-01-01T00:00:00"))
        row = self.global_conn.execute("SELECT amount FROM balance_snapshots WHERE id = ?", (snap_id,)).fetchone()
        self.assertEqual(row["amount"], 1000.0)

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        eid = self._entity_a()
        snap_id = queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        self.assertFalse(queries.delete_balance_snapshot(self.conn_b, snap_id))
        self.assertIsNotNone(queries.get_balance_snapshot(self.conn_a, snap_id))


class TestSchedulesIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        sch_id = queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        row = self.global_conn.execute("SELECT profile_id FROM schedules WHERE id = ?", (sch_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_all_is_scoped(self):
        self._seed_shared()
        queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        self.assertEqual(queries.get_all_schedules(self.conn_b), [])
        self.assertEqual(len(queries.get_all_schedules(self.conn_a)), 1)

    def test_get_single_is_scoped(self):
        self._seed_shared()
        sch_id = queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        self.assertIsNone(queries.get_schedule(self.conn_b, sch_id))
        self.assertIsNotNone(queries.get_schedule(self.conn_a, sch_id))


class TestScheduleOccurrencesIsolation(IsolationBase):
    def test_insert_stamps_profile_id(self):
        self._seed_shared()
        sch_id = queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        tx_id = self._transaction_a()
        queries.insert_schedule_occurrence(self.conn_a, sch_id, "2026-01-01", tx_id)
        row = self.global_conn.execute(
            "SELECT profile_id FROM schedule_occurrences WHERE schedule_id = ? AND occurrence_date = ?",
            (sch_id, "2026-01-01"),
        ).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_occurrence_is_scoped(self):
        self._seed_shared()
        sch_id = queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        tx_id = self._transaction_a()
        queries.insert_schedule_occurrence(self.conn_a, sch_id, "2026-01-01", tx_id)
        self.assertIsNone(queries.get_schedule_occurrence(self.conn_b, sch_id, "2026-01-01"))
        self.assertIsNotNone(queries.get_schedule_occurrence(self.conn_a, sch_id, "2026-01-01"))

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        sch_id = queries.create_schedule(self.conn_a, "Monthly buy", "2026-01-01", "MONTHLY")
        tx_id = self._transaction_a()
        queries.insert_schedule_occurrence(self.conn_a, sch_id, "2026-01-01", tx_id)
        queries.delete_schedule_occurrences(self.conn_b, sch_id)
        self.assertIsNotNone(queries.get_schedule_occurrence(self.conn_a, sch_id, "2026-01-01"))


class TestManualValuesIsolation(IsolationBase):
    def test_create_stamps_profile_id(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        mv_id = queries.create_manual_value(self.conn_a, pa_id, 500.0, "2026-01-01")
        row = self.global_conn.execute("SELECT profile_id FROM manual_values WHERE id = ?", (mv_id,)).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)

    def test_get_values_is_scoped(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        queries.create_manual_value(self.conn_a, pa_id, 500.0, "2026-01-01")
        self.assertEqual(queries.get_manual_values(self.conn_b, pa_id), [])
        self.assertEqual(len(queries.get_manual_values(self.conn_a, pa_id)), 1)

    def test_latest_and_as_of_are_scoped(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        queries.create_manual_value(self.conn_a, pa_id, 500.0, "2026-01-01")
        self.assertIsNone(queries.get_latest_manual_value(self.conn_b, pa_id))
        self.assertIsNone(queries.get_manual_value_as_of(self.conn_b, pa_id, "2026-06-01"))
        self.assertIsNotNone(queries.get_latest_manual_value(self.conn_a, pa_id))

    def test_delete_cross_profile_is_noop(self):
        self._seed_shared()
        pa_id = self._portfolio_asset_a()
        mv_id = queries.create_manual_value(self.conn_a, pa_id, 500.0, "2026-01-01")
        self.assertFalse(queries.delete_manual_value(self.conn_b, mv_id))
        self.assertIsNotNone(queries.get_latest_manual_value(self.conn_a, pa_id))


class TestDependencyChecksIsolation(IsolationBase):
    def _seed_dependents(self):
        self._seed_shared()
        eid = self._entity_a()
        pa_id = self._portfolio_asset_a()
        fe_id = queries.create_fiscal_exemption(self.conn_a, "NONE_TAX")
        tx_id = queries.create_transaction(
            self.conn_a,
            timestamp="2026-01-01T00:00:00",
            type_="INVESTMENT_BUY",
            entity_id=eid,
            currency="EUR",
            total_value=100.0,
            portfolio_asset_id=pa_id,
            fiscal_exemption_id=fe_id,
        )
        queries.create_fee(self.conn_a, tx_id, "BROKER", "FIXED", "EUR")
        queries.create_balance_snapshot(self.conn_a, eid, "EUR", 1000.0, "2026-01-01T00:00:00")
        return eid, pa_id, fe_id, tx_id

    def test_ownership_dependency_checks_are_scoped(self):
        eid, pa_id, fe_id, tx_id = self._seed_dependents()
        for check, arg in [
            (queries.entity_has_dependents, eid),
            (queries.entity_has_assets, eid),
            (queries.portfolio_asset_has_dependents, pa_id),
            (queries.transaction_has_dependents, tx_id),
            (queries.fiscal_exemption_has_dependents, fe_id),
        ]:
            self.assertFalse(check(self.conn_b, arg), f"{check.__name__} leaked across profiles")
            self.assertTrue(check(self.conn_a, arg), f"{check.__name__} missing own profile data")

    def test_market_asset_ownership_dependency_is_scoped(self):
        """portfolio_assets is ownership data (scoped); only the prices
        subquery is shared reference data."""
        self._seed_shared()
        self._portfolio_asset_a()
        self.assertFalse(queries.market_asset_has_dependents(self.conn_b, "TEST"))
        self.assertTrue(queries.market_asset_has_dependents(self.conn_a, "TEST"))

    def test_currency_ownership_dependency_is_scoped(self):
        """The ownership subqueries (transactions/fees/taxes/snapshots) are
        profile-scoped; only the shared market_assets subquery is global."""
        self._seed_dependents()
        self.assertFalse(queries.currency_code_has_dependents(self.conn_b, "EUR"))
        self.assertTrue(queries.currency_code_has_dependents(self.conn_a, "EUR"))
        self.assertTrue(queries.currency_code_has_dependents(self.conn_b, "USD"))
        self.assertTrue(queries.currency_code_has_dependents(self.conn_a, "USD"))

    def test_has_transactions_and_schedules_scoped(self):
        eid, _, _, _ = self._seed_dependents()
        queries.create_schedule(self.conn_a, "Monthly", "2026-01-01", "MONTHLY", entity_id=eid, currency="EUR")
        self.assertFalse(queries.has_transactions_on_or_after(self.conn_b, eid, "EUR", "2020-01-01"))
        self.assertFalse(queries.has_schedules_on_or_before(self.conn_b, eid, "EUR", "2030-01-01"))
        self.assertTrue(queries.has_transactions_on_or_after(self.conn_a, eid, "EUR", "2020-01-01"))
        self.assertTrue(queries.has_schedules_on_or_before(self.conn_a, eid, "EUR", "2030-01-01"))


class TestAnalyticsIsolation(IsolationBase):
    def _seed_holdings(self):
        self._seed_shared()
        eid = self._entity_a()
        pa_id = self._portfolio_asset_a()
        queries.create_transaction(
            self.conn_a,
            timestamp="2026-01-01T00:00:00",
            type_="INVESTMENT_BUY",
            entity_id=eid,
            currency="USD",
            total_value=100.0,
            portfolio_asset_id=pa_id,
            quantity=10.0,
            unit_price=10.0,
        )
        queries.create_balance_snapshot(self.conn_a, eid, "USD", 1000.0, "2026-01-01T00:00:00")
        queries.create_schedule(self.conn_a, "Monthly", "2026-01-01", "MONTHLY", entity_id=eid, currency="USD")
        queries.create_manual_value(self.conn_a, pa_id, 500.0, "2026-01-01")
        self.conn_a.commit()

    def test_analytics_queries_are_scoped(self):
        self._seed_holdings()
        eid = self.conn_a.execute("SELECT id FROM entities LIMIT 1").fetchone()["id"]
        self.assertEqual(analytics_queries.get_holdings_raw(self.conn_b), [])
        self.assertEqual(analytics_queries.get_holdings_by_entity_raw(self.conn_b), [])
        self.assertEqual(analytics_queries.get_cash_flow_raw(self.conn_b, "month"), [])
        self.assertEqual(analytics_queries.get_cash_balance_by_currency(self.conn_b), [])
        self.assertEqual(queries.get_manual_tracked_assets(self.conn_b), [])
        self.assertEqual(analytics_queries.get_entity_cash_as_of(self.conn_b, eid, "2026-06-01T00:00:00"), 0.0)
        self.assertEqual(queries.get_balance_at_date(self.conn_b, eid, "USD", "2026-06-01T00:00:00"), 0.0)
        self.assertEqual(
            analytics_queries.get_entity_cash_by_currency_as_of(self.conn_b, eid, "2026-06-01T00:00:00"), {}
        )
        self.assertEqual(
            analytics_queries.get_entity_total_cash_by_currency_as_of(self.conn_b, eid, "2026-06-01T00:00:00"),
            {},
        )

    def test_analytics_see_own_profile(self):
        self._seed_holdings()
        self.assertEqual(len(analytics_queries.get_holdings_raw(self.conn_a)), 1)
        self.assertEqual(len(analytics_queries.get_cash_flow_raw(self.conn_a, "month")), 1)
        self.assertEqual(len(analytics_queries.get_cash_balance_by_currency(self.conn_a)), 1)


class TestScopedConnections(IsolationBase):
    def test_profile_clause_is_empty_when_unscoped(self):
        conn = make_conn()
        self.assertEqual(queries._profile_clause(conn), "")
        self.assertEqual(queries._profile_params(conn), ())
        conn.close()

    def test_profile_clause_carries_profile(self):
        self.assertEqual(queries._profile_clause(self.conn_a), " AND profile_id = ?")
        self.assertEqual(queries._profile_params(self.conn_a), (self.profile_a,))

    def test_unscoped_connection_sees_all_profiles(self):
        self._seed_shared()
        self._entity_a()
        queries.create_entity(self.conn_b, "Broker B", EntityType.BANK)
        conn = make_conn(name=self.db_name)
        try:
            self.assertEqual(len(queries.get_all_entities(conn)), 2)
        finally:
            conn.close()


class TestContextVarProfile(unittest.TestCase):
    @staticmethod
    def _scoped(conn):
        return cast(ProfileScopedConnection, conn)

    def test_explicit_profile_id_beats_contextvar(self):
        token = set_active_profile(7)
        try:
            conn = get_db(profile_id=3)
            try:
                self.assertEqual(self._scoped(conn).profile_id, 3)
            finally:
                conn.close()
        finally:
            reset_active_profile(token)

    def test_get_db_reads_contextvar(self):
        token = set_active_profile(9)
        try:
            conn = get_db()
            try:
                self.assertEqual(self._scoped(conn).profile_id, 9)
            finally:
                conn.close()
        finally:
            reset_active_profile(token)

    def test_reset_restores_previous_value(self):
        self.assertIsNone(self._scoped(get_db()).profile_id)
        token = set_active_profile(9)
        try:
            conn = get_db()
            try:
                self.assertEqual(self._scoped(conn).profile_id, 9)
            finally:
                conn.close()
        finally:
            reset_active_profile(token)
        conn = get_db()
        try:
            self.assertIsNone(self._scoped(conn).profile_id)
        finally:
            conn.close()
