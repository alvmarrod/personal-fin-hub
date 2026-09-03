import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from db.connection import ProfileScopedConnection
from models import (
    BatchCreate,
    FullTransactionCreate,
    TransactionCreate,
    TransactionFeeInner,
    TransactionTaxInner,
)
from models.enums import EntityType, FeeNature, FeeType, TransactionType
from routes.transactions import router
from services.transaction_svc import FKNotFound as TxFKNotFound

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> ProfileScopedConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False, factory=ProfileScopedConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_entity(conn: sqlite3.Connection) -> int:
    return queries.create_entity(conn, "Test Broker", EntityType.BROKER)


def seed_currency(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "USD", "USD", 1.0, datetime(2024, 1, 1, 0, 0, 0))


def seed_currency_pair(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "EUR", "USD", 1.1, datetime(2024, 1, 1, 0, 0, 0))


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


def default_tx_body(**overrides):
    body = {
        "timestamp": "2024-06-01T10:00:00",
        "type": "INVESTMENT_BUY",
        "entity_id": 1,
        "currency": "USD",
        "quantity": 10.0,
        "unit_price": 50.0,
        "notes": None,
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestTransactionQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_transactions(self.conn), [])

    def test_create_returns_id(self):
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_BUY",
            entity_id=self.eid,
            currency="USD",
            total_value=500.0,
            quantity=10.0,
            unit_price=50.0,
            notes="test note",
        )
        self.assertIsInstance(tx_id, int)
        self.assertGreater(tx_id, 0)

    def test_get_returns_row(self):
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        row = queries.get_transaction(self.conn, tx_id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["type"], "INVESTMENT_SELL")
        self.assertEqual(row["entity_id"], self.eid)
        self.assertEqual(row["total_value"], 100.0)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_transaction(self.conn, 999))

    def test_list_all(self):
        queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_BUY",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T11:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=200.0,
        )
        self.assertEqual(len(queries.get_all_transactions(self.conn)), 2)

    def test_list_by_entity(self):
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_BUY",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        rows = queries.get_transactions_by_entity(self.conn, self.eid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], tx_id)

    def test_list_by_entity_empty(self):
        self.assertEqual(queries.get_transactions_by_entity(self.conn, 999), [])

    def test_update_returns_true(self):
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_BUY",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        ok = queries.update_transaction(
            self.conn,
            tx_id,
            timestamp="2024-06-02T10:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=200.0,
        )
        self.assertTrue(ok)
        row = queries.get_transaction(self.conn, tx_id)
        assert row is not None
        self.assertEqual(row["type"], "INVESTMENT_SELL")
        self.assertEqual(row["total_value"], 200.0)

    def test_update_nonexistent(self):
        ok = queries.update_transaction(
            self.conn,
            999,
            timestamp="2024-06-01T10:00:00",
            type_="BUY",
            entity_id=self.eid,
            currency="USD",
        )
        self.assertFalse(ok)

    def test_create_sell_falls_back_to_profile_default_rule(self):
        self.conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
        self.conn.execute("UPDATE profiles SET default_fiscal_rule = 'japan' WHERE id = 1")
        self.conn.profile_id = 1
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        row = queries.get_transaction(self.conn, tx_id)
        assert row is not None
        self.assertEqual(row["fiscal_rule"], "japan")
        ok = queries.update_transaction(
            self.conn,
            tx_id,
            timestamp="2024-07-01T10:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        self.assertTrue(ok)
        row = queries.get_transaction(self.conn, tx_id)
        assert row is not None
        self.assertEqual(row["fiscal_rule"], "japan")

    def test_create_sell_without_period_or_default_stays_null(self):
        self.conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
        self.conn.profile_id = 1
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_SELL",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        row = queries.get_transaction(self.conn, tx_id)
        assert row is not None
        self.assertIsNone(row["fiscal_rule"])

    def test_delete_returns_true(self):
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INVESTMENT_BUY",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        ok = queries.delete_transaction(self.conn, tx_id)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_transaction(self.conn, tx_id))

    def test_delete_nonexistent(self):
        ok = queries.delete_transaction(self.conn, 999)
        self.assertFalse(ok)


class TestTransactionService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def test_create(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=10.0,
            unit_price=50.0,
        )
        result = svc.create(body)
        self.assertEqual(result.type, TransactionType.INVESTMENT_BUY)
        self.assertEqual(result.total_value, 500.0)
        self.assertIsNotNone(result.id)

    def test_create_with_income_category(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INCOME,
            entity_id=self.eid,
            currency="USD",
            total_value=3000.0,
            income_category="salary",
        )
        result = svc.create(body)
        from models import IncomeCategory

        self.assertEqual(result.income_category, IncomeCategory.SALARY)
        fetched = svc.get(result.id)
        self.assertEqual(fetched.income_category, IncomeCategory.SALARY)

    def test_create_with_explicit_total_value(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=10.0,
            unit_price=50.0,
            total_value=999.0,
        )
        result = svc.create(body)
        self.assertEqual(result.total_value, 999.0)

    def test_create_without_total_value_auto(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=10.0,
            unit_price=50.0,
            total_value=None,
        )
        result = svc.create(body)
        self.assertEqual(result.total_value, 500.0)

    def test_create_with_notes(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=10.0,
            unit_price=50.0,
            notes="my annotation",
        )
        result = svc.create(body)
        self.assertEqual(result.notes, "my annotation")

    def test_create_missing_fk_entity(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=999,
            currency="USD",
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)

    def test_create_missing_fk_currency(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="XYZ",
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=5.0,
            unit_price=20.0,
        )
        created = svc.create(body)
        result = svc.get(created.id)
        self.assertEqual(result.id, created.id)

    def test_get_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_svc()
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 2, 10, 0, 0),
                type=TransactionType.INVESTMENT_SELL,
                entity_id=self.eid,
                currency="USD",
            )
        )
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.list_all(), [])

    def test_list_all_with_date_filter(self):
        svc = self.import_svc()
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 15, 10, 0, 0),
                type=TransactionType.INVESTMENT_SELL,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 7, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )

        # Filter by date range
        result = svc.list_all(start_date="2024-06-10", end_date="2024-06-20")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, TransactionType.INVESTMENT_SELL)

    def test_list_all_with_type_filter(self):
        svc = self.import_svc()
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 2, 10, 0, 0),
                type=TransactionType.INVESTMENT_SELL,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 3, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )

        result = svc.list_all(type_filter="INVESTMENT_SELL")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, TransactionType.INVESTMENT_SELL)

    def test_list_all_with_entity_filter(self):
        svc = self.import_svc()
        eid2 = queries.create_entity(self.conn, "Another Entity", EntityType.BANK)

        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 2, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=eid2,
                currency="USD",
            )
        )

        result = svc.list_all(entity_id=self.eid)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entity_id, self.eid)

    def test_list_all_with_currency_filter(self):
        svc = self.import_svc()
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 2, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
            )
        )

        result = svc.list_all(currency="EUR")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].currency, "EUR")

    def test_list_all_with_multiple_filters(self):
        svc = self.import_svc()
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 15, 10, 0, 0),
                type=TransactionType.INVESTMENT_SELL,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 7, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="EUR",
            )
        )

        result = svc.list_all(
            start_date="2024-06-01",
            end_date="2024-06-30",
            type_filter="INVESTMENT_BUY",
            currency="USD",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].timestamp.day, 1)

    def test_get_full(self):
        svc = self.import_svc()
        created = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        result = svc.get_full(created.id)
        self.assertIsNotNone(result["transaction"])
        self.assertEqual(result["transaction"].id, created.id)
        self.assertEqual(result["fees"], [])
        self.assertEqual(result["taxes"], [])

    def test_get_full_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.get_full(999)

    def test_update_full_deletes_removed_fees_and_taxes(self):
        from models import TransactionFeeInner, TransactionTaxInner
        from services import transaction_full_svc

        svc = self.import_svc()
        created = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        body = transaction_full_svc.FullTransactionCreate(
            transaction=svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            fees=[
                TransactionFeeInner(
                    fee_type=FeeType.BROKER,
                    nature=FeeNature.FIXED,
                    fixed_amount=1.5,
                    currency="USD",
                )
            ],
            taxes=[
                TransactionTaxInner(
                    tax_type="WITHHOLDING",
                    tax_amount=2.0,
                    currency="USD",
                )
            ],
        )
        with patch("services.transaction_full_svc.get_db", return_value=self.conn):
            full = transaction_full_svc.create(body)
            self.assertEqual(len(full.fees), 1)
            self.assertEqual(len(full.taxes), 1)

            updated = transaction_full_svc.update_full(
                created.id,
                body.model_copy(update={"fees": [], "taxes": []}),
            )
            self.assertEqual(updated.fees, [])
            self.assertEqual(updated.taxes, [])

        result = svc.get_full(created.id)
        self.assertEqual(result["fees"], [])
        self.assertEqual(result["taxes"], [])

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        result = svc.update(
            created.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 2, 10, 0, 0),
                type=TransactionType.INVESTMENT_SELL,
                entity_id=self.eid,
                currency="USD",
                quantity=5.0,
                unit_price=40.0,
                total_value=200.0,
            ),
        )
        self.assertEqual(result.type, TransactionType.INVESTMENT_SELL)
        self.assertEqual(result.total_value, 200.0)
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.update(
                999,
                svc.TransactionCreate(
                    timestamp=datetime(2024, 6, 1, 10, 0, 0),
                    type=TransactionType.INVESTMENT_BUY,
                    entity_id=self.eid,
                    currency="USD",
                ),
            )

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
            )
        )
        svc.delete(created.id)
        with self.assertRaises(svc.TransactionNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.delete(999)

    def test_create_with_multiple_fks(self):
        queries.create_market_asset(
            self.conn,
            market_code="AAPL.US",
            currency_code="USD",
            asset_type="STOCK",
            ticker="AAPL",
        )
        pa_id = queries.create_portfolio_asset(
            self.conn,
            market_code="AAPL.US",
        )
        fe_id = queries.create_fiscal_exemption(
            self.conn,
            exemption_type="WITHHOLDING_TAX",
            description="US withholding",
            exemption_rate=0.15,
        )
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
            portfolio_asset_id=pa_id,
            payment_currency="EUR",
            fx_rate=1.1,
            settlement_date=datetime(2024, 6, 5, 0, 0, 0),
            fiscal_exemption_id=fe_id,
            dividend_type=None,
            record_date=None,
            payment_date=None,
            dividend_currency=None,
            dividend_payment_currency=None,
            dividend_fx_rate=None,
            notes="multi-fk tx",
        )
        result = svc.create(body)
        self.assertEqual(result.total_value, 100.0)
        self.assertEqual(result.portfolio_asset_id, pa_id)
        self.assertEqual(result.fiscal_exemption_id, fe_id)
        self.assertEqual(result.notes, "multi-fk tx")


class TestBalanceAdjustmentLinks(unittest.TestCase):
    """Phase A persistence: cash_handling + balance_adjustment_links."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def _buy(self, **overrides):
        from models.enums import TransactionType

        svc = self.import_svc()
        kwargs = {
            "timestamp": datetime(2024, 6, 1, 10, 0, 0),
            "type": TransactionType.INVESTMENT_BUY,
            "entity_id": self.eid,
            "currency": "USD",
            "quantity": 10.0,
            "unit_price": 50.0,
        }
        kwargs.update(overrides)
        return svc.create(svc.TransactionCreate(**kwargs))

    def test_create_persists_cash_handling_and_links_injection(self):
        from models.enums import BalanceMode

        result = self._buy(cash_handling=BalanceMode.INJECT)
        self.assertEqual(result.cash_handling, BalanceMode.INJECT)

        row = queries.get_transaction(self.conn, result.id)
        assert row is not None
        self.assertEqual(row["cash_handling"], "inject")

        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [result.id])

    def test_create_debit_mode_skips_injection_and_link(self):
        from models.enums import BalanceMode

        result = self._buy(cash_handling=BalanceMode.DEBIT)
        self.assertEqual(result.cash_handling, BalanceMode.DEBIT)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        self.assertIsNone(adj)
        row = self.conn.execute("SELECT COUNT(*) AS c FROM balance_adjustment_links").fetchone()
        self.assertEqual(row["c"], 0)

    def test_default_mode_stays_null_but_links_injection(self):
        result = self._buy()
        self.assertIsNone(result.cash_handling)
        row = queries.get_transaction(self.conn, result.id)
        assert row is not None
        self.assertIsNone(row["cash_handling"])
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [result.id])

    def test_same_day_spends_share_linked_injection(self):
        first = self._buy(timestamp=datetime(2025, 6, 1, 0, 0, 0))
        second = self._buy(timestamp=datetime(2025, 6, 1, 0, 0, 0), quantity=6.0, unit_price=50.0)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-05-31T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(adj["total_value"], 800.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [first.id, second.id])

    def test_delete_last_spend_removes_attached_injection(self):
        result = self._buy()
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        assert adj is not None

        svc = self.import_svc()
        svc.delete(result.id)

        self.assertIsNone(queries.get_transaction(self.conn, adj["id"]))
        row = self.conn.execute("SELECT COUNT(*) AS c FROM balance_adjustment_links").fetchone()
        self.assertEqual(row["c"], 0)

    def test_delete_one_of_two_spends_keeps_merged_injection(self):
        first = self._buy(timestamp=datetime(2025, 6, 1, 0, 0, 0))
        second = self._buy(timestamp=datetime(2025, 6, 1, 0, 0, 0), quantity=6.0, unit_price=50.0)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-05-31T23:59:59")
        assert adj is not None

        svc = self.import_svc()
        svc.delete(first.id)

        surviving = queries.get_transaction(self.conn, adj["id"])
        self.assertIsNotNone(surviving)
        assert surviving is not None
        self.assertEqual(surviving["total_value"], 800.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [second.id])

    def test_get_adjustment_returns_attached_ids_and_cash_handling_none(self):
        buy = self._buy()
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        assert adj is not None

        svc = self.import_svc()
        fetched = svc.get(adj["id"])
        self.assertIsNone(fetched.cash_handling)
        self.assertEqual(fetched.attached_transaction_ids, [buy.id])

        fetched_buy = svc.get(buy.id)
        self.assertIsNone(fetched_buy.attached_transaction_ids)

    def test_delete_adjustment_clears_its_links(self):
        self._buy()
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        assert adj is not None

        svc = self.import_svc()
        svc.delete(adj["id"])

        row = self.conn.execute("SELECT COUNT(*) AS c FROM balance_adjustment_links").fetchone()
        self.assertEqual(row["c"], 0)

    def test_update_without_cash_handling_preserves_persisted_mode(self):
        from models.enums import TransactionType

        result = self._buy(cash_handling="inject")
        svc = self.import_svc()
        svc.update(
            result.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=20.0,
                unit_price=50.0,
            ),
        )
        fetched = svc.get(result.id)
        self.assertEqual(fetched.cash_handling.value, "inject")
        row = queries.get_transaction(self.conn, result.id)
        assert row is not None
        self.assertEqual(row["cash_handling"], "inject")

    def test_update_with_explicit_cash_handling_overrides(self):
        from models.enums import TransactionType

        result = self._buy(cash_handling="inject")
        svc = self.import_svc()
        updated = svc.update(
            result.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=20.0,
                unit_price=50.0,
                cash_handling="debit",
            ),
        )
        self.assertEqual(updated.cash_handling.value, "debit")

    def test_update_with_explicit_null_clears_to_auto(self):
        from models.enums import TransactionType

        result = self._buy(cash_handling="inject")
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=20.0,
            unit_price=50.0,
            cash_handling=None,
        )
        self.assertIn("cash_handling", body.model_fields_set)
        updated = svc.update(result.id, body)
        self.assertIsNone(updated.cash_handling)
        row = queries.get_transaction(self.conn, result.id)
        assert row is not None
        self.assertIsNone(row["cash_handling"])


class TestEditTimeInjectionLifecycle(unittest.TestCase):
    """Phase B: attached injections are recalculated when their spends are edited."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def _inj(self, ts):
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", ts)
        return adj

    def test_edit_raises_attached_injection(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        buy = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        svc.update(
            buy.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=16.0,
                unit_price=50.0,
            ),
        )
        adj = self._inj("2024-05-31T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(adj["total_value"], 800.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [buy.id])

    def test_edit_lowers_attached_injection(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        buy = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        svc.update(
            buy.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=6.0,
                unit_price=50.0,
            ),
        )
        adj = self._inj("2024-05-31T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(adj["total_value"], 300.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [buy.id])

    def test_edit_removes_injection_when_fully_funded(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        buy = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 5, 25, 9, 0, 0),
                type=TransactionType.INCOME,
                entity_id=self.eid,
                currency="USD",
                total_value=700.0,
                income_category="salary",
            )
        )
        svc.update(
            buy.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=6.0,
                unit_price=50.0,
            ),
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))
        row = self.conn.execute("SELECT COUNT(*) AS c FROM balance_adjustment_links").fetchone()
        self.assertEqual(row["c"], 0)

    def test_move_spend_to_new_date_relinks(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        buy = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        svc.update(
            buy.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 5, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))
        adj = self._inj("2024-06-04T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertEqual(adj["total_value"], 500.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, adj["id"]), [buy.id])

    def test_type_change_to_income_detaches_and_removes_injection(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        tx = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        updated = svc.update(
            tx.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INCOME,
                entity_id=self.eid,
                currency="USD",
                total_value=200.0,
                income_category="other",
            ),
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))
        row = self.conn.execute("SELECT COUNT(*) AS c FROM balance_adjustment_links").fetchone()
        self.assertEqual(row["c"], 0)
        self.assertEqual(updated.type, TransactionType.INCOME)

    def test_entity_move_moves_attachment(self):
        from models.enums import EntityType, TransactionType

        other_eid = queries.create_entity(self.conn, "Other Broker", EntityType.BANK)
        svc = self.import_svc()
        buy = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        svc.update(
            buy.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=other_eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))
        moved_adj = queries.get_injected_adjustment_at(self.conn, other_eid, "USD", "2024-05-31T23:59:59")
        self.assertIsNotNone(moved_adj)
        assert moved_adj is not None
        self.assertEqual(moved_adj["total_value"], 500.0)
        self.assertEqual(queries.get_attached_transaction_ids(self.conn, moved_adj["id"]), [buy.id])

    def test_merged_pair_edit_recalculates_combined_requirement(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        first = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 0, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            )
        )
        second = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 0, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=6.0,
                unit_price=50.0,
            )
        )
        adj = self._inj("2024-05-31T23:59:59")
        assert adj is not None
        self.assertEqual(adj["total_value"], 800.0)

        svc.update(
            first.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 0, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=18.0,
                unit_price=50.0,
            ),
        )
        refreshed = self._inj("2024-05-31T23:59:59")
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed["total_value"], 1200.0)
        self.assertEqual(
            sorted(queries.get_attached_transaction_ids(self.conn, refreshed["id"])), sorted([first.id, second.id])
        )

    def test_debit_mode_edit_never_injects(self):
        from models.enums import TransactionType

        svc = self.import_svc()
        out = svc.create(
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.MONEY_OUT,
                entity_id=self.eid,
                currency="USD",
                total_value=500.0,
                cash_handling="debit",
            )
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))
        svc.update(
            out.id,
            svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.MONEY_OUT,
                entity_id=self.eid,
                currency="USD",
                total_value=900.0,
                cash_handling="debit",
            ),
        )
        self.assertIsNone(self._inj("2024-05-31T23:59:59"))


class TestTransactionRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/transactions")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post(
            "/api/v1/transactions",
            json={
                "timestamp": "2024-06-01T10:00:00",
                "type": "INVESTMENT_BUY",
                "entity_id": self.eid,
                "currency": "USD",
                "quantity": 10.0,
                "unit_price": 50.0,
                "notes": "test note",
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["type"], "INVESTMENT_BUY")
        self.assertEqual(data["total_value"], 500.0)
        self.assertEqual(data["notes"], "test note")
        self.assertIn("id", data)
        # Verify normalized format: no Z, no microseconds
        self.assertRegex(data["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_create_normalizes_utc_timestamp(self):
        """Z-suffixed timestamps are stored without Z or microseconds."""
        resp = client.post(
            "/api/v1/transactions",
            json=default_tx_body(timestamp="2024-06-01T10:00:00.000Z"),
        )
        self.assertEqual(resp.status_code, 201)
        tx_id = resp.json()["id"]
        row = self.conn.execute("SELECT timestamp FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        self.assertEqual(row["timestamp"], "2024-06-01T10:00:00")

    def test_create_bad_fk(self):
        resp = client.post("/api/v1/transactions", json=default_tx_body(entity_id=999))
        self.assertEqual(resp.status_code, 400)

    def test_create_bad_currency(self):
        resp = client.post("/api/v1/transactions", json=default_tx_body(currency="XYZ"))
        self.assertEqual(resp.status_code, 400)

    def test_get(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/transactions/{tx_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], tx_id)

    def test_get_not_found(self):
        resp = client.get("/api/v1/transactions/999")
        self.assertEqual(resp.status_code, 404)

    def test_list(self):
        client.post("/api/v1/transactions", json=default_tx_body())
        client.post(
            "/api/v1/transactions",
            json=default_tx_body(
                timestamp="2024-06-02T10:00:00",
                type="INVESTMENT_SELL",
            ),
        )
        resp = client.get("/api/v1/transactions")
        # Unfunded first buy adds one injected BALANCE_ADJUSTMENT to the list
        self.assertEqual(len(resp.json()), 3)

    def test_update(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/transactions/{tx_id}",
            json={
                "timestamp": "2024-06-02T10:00:00",
                "type": "INVESTMENT_SELL",
                "entity_id": self.eid,
                "currency": "USD",
                "quantity": 5.0,
                "unit_price": 60.0,
                "total_value": 300.0,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["type"], "INVESTMENT_SELL")
        self.assertEqual(resp.json()["total_value"], 300.0)

    def test_update_not_found(self):
        resp = client.put("/api/v1/transactions/999", json=default_tx_body())
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/transactions/{tx_id}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/transactions/{tx_id}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/transactions/999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_with_fees_409(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        self.conn.execute(
            "INSERT INTO transaction_fees (transaction_id, fee_type, nature, currency, fixed_amount) VALUES (?, ?, ?, ?, ?)",
            (tx_id, "BROKER", "FIXED", "USD", 10.0),
        )
        resp = client.delete(f"/api/v1/transactions/{tx_id}")
        self.assertEqual(resp.status_code, 409)

    def test_get_full(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/transactions/{tx_id}/full")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("transaction", data)
        self.assertIn("fees", data)
        self.assertIn("taxes", data)
        self.assertEqual(data["transaction"]["id"], tx_id)
        self.assertEqual(data["fees"], [])
        self.assertEqual(data["taxes"], [])

    def test_get_full_not_found(self):
        resp = client.get("/api/v1/transactions/999/full")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Composite full-transaction tests
# ---------------------------------------------------------------------------


class TestFullTransactionService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patchers = [
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.transaction_fee_svc.get_db", return_value=self.conn),
            patch("services.transaction_tax_svc.get_db", return_value=self.conn),
            patch("services.transaction_full_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_full_svc

        return transaction_full_svc

    def import_tx_svc(self):
        from services import transaction_svc

        return transaction_svc

    def test_create_tx_only(self):
        svc = self.import_svc()
        body = FullTransactionCreate(
            transaction=TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
        )
        result = svc.create(body)
        self.assertEqual(result.transaction.total_value, 500.0)
        self.assertEqual(result.fees, [])
        self.assertEqual(result.taxes, [])

    def test_create_tx_with_fees(self):
        svc = self.import_svc()
        body = FullTransactionCreate(
            transaction=TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            fees=[
                TransactionFeeInner(
                    fee_type=FeeType.BROKER,
                    nature=FeeNature.FIXED,
                    currency="USD",
                    fixed_amount=5.0,
                ),
            ],
        )
        result = svc.create(body)
        self.assertEqual(result.transaction.total_value, 500.0)
        self.assertEqual(len(result.fees), 1)
        self.assertEqual(result.fees[0].fixed_amount, 5.0)
        self.assertEqual(result.fees[0].transaction_id, result.transaction.id)
        self.assertEqual(result.taxes, [])

    def test_create_tx_with_fees_and_taxes(self):
        svc = self.import_svc()
        body = FullTransactionCreate(
            transaction=TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            fees=[
                TransactionFeeInner(
                    fee_type=FeeType.BROKER,
                    nature=FeeNature.FIXED,
                    currency="USD",
                    fixed_amount=5.0,
                ),
            ],
            taxes=[
                TransactionTaxInner(
                    tax_type="STAMP_DUTY",
                    tax_amount=2.0,
                    currency="USD",
                    tax_rate=0.005,
                ),
            ],
        )
        result = svc.create(body)
        self.assertEqual(result.transaction.total_value, 500.0)
        self.assertEqual(len(result.fees), 1)
        self.assertEqual(len(result.taxes), 1)
        self.assertEqual(result.taxes[0].transaction_id, result.transaction.id)
        self.assertEqual(result.taxes[0].tax_amount, 2.0)

    def test_create_rollback_on_bad_fk(self):
        svc = self.import_svc()
        tx_svc = self.import_tx_svc()
        body = FullTransactionCreate(
            transaction=TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=999,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            fees=[
                TransactionFeeInner(
                    fee_type=FeeType.BROKER,
                    nature=FeeNature.FIXED,
                    currency="USD",
                    fixed_amount=5.0,
                ),
            ],
        )
        with self.assertRaises(TxFKNotFound):
            svc.create(body)
        all_tx = tx_svc.list_all()
        self.assertEqual(len(all_tx), 0, "Transaction should not exist after rollback")

    def test_buys_same_day_merge_injection(self):
        tx_svc = self.import_tx_svc()
        # Same-date buys at T00:00:00 share (date – 1 day) → identical injection_ts
        tx_svc.create(
            TransactionCreate(
                timestamp=datetime(2025, 6, 1, 0, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            conn=self.conn,
        )
        tx_svc.create(
            TransactionCreate(
                timestamp=datetime(2025, 6, 1, 0, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=6.0,
                unit_price=50.0,
            ),
            conn=self.conn,
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 0)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-05-31T23:59:59")
        self.assertIsNotNone(adj, "Same-day buys should share one injection")
        assert adj is not None
        self.assertEqual(adj["total_value"], 800.0, "Injection should cover both buys (500 + 300)")

        balance = queries.get_balance_at_date(self.conn, self.eid, "USD", "2026-01-01T00:00:00")
        self.assertEqual(balance, 0.0, "Both buys deducted → net zero")

    def test_buys_different_days_separate_injections(self):
        tx_svc = self.import_tx_svc()
        tx_svc.create(
            TransactionCreate(
                timestamp=datetime(2025, 6, 1, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
            conn=self.conn,
        )
        tx_svc.create(
            TransactionCreate(
                timestamp=datetime(2025, 6, 5, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                quantity=6.0,
                unit_price=50.0,
            ),
            conn=self.conn,
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 0)
        adj1 = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-05-31T23:59:59")
        adj2 = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-06-04T23:59:59")
        self.assertIsNotNone(adj1)
        self.assertIsNotNone(adj2)
        assert adj1 is not None
        assert adj2 is not None
        self.assertEqual(adj1["total_value"], 500.0)
        self.assertEqual(adj2["total_value"], 300.0)


class TestFullTransactionRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patchers = [
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.transaction_fee_svc.get_db", return_value=self.conn),
            patch("services.transaction_tax_svc.get_db", return_value=self.conn),
            patch("services.transaction_full_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def test_create_full_tx_only(self):
        resp = client.post(
            "/api/v1/transactions/full",
            json={
                "transaction": {
                    "timestamp": "2024-06-01T10:00:00",
                    "type": "INVESTMENT_BUY",
                    "entity_id": self.eid,
                    "currency": "USD",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                },
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["transaction"]["total_value"], 500.0)
        self.assertEqual(data["fees"], [])
        self.assertEqual(data["taxes"], [])

    def test_create_full_with_fees_and_taxes(self):
        resp = client.post(
            "/api/v1/transactions/full",
            json={
                "transaction": {
                    "timestamp": "2024-06-01T10:00:00",
                    "type": "INVESTMENT_BUY",
                    "entity_id": self.eid,
                    "currency": "USD",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                    "notes": "composite test",
                },
                "fees": [
                    {
                        "fee_type": "BROKER",
                        "nature": "FIXED",
                        "currency": "USD",
                        "fixed_amount": 5.0,
                    },
                ],
                "taxes": [
                    {
                        "tax_type": "STAMP_DUTY",
                        "tax_amount": 2.0,
                        "currency": "USD",
                        "tax_rate": 0.005,
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["transaction"]["notes"], "composite test")
        self.assertEqual(len(data["fees"]), 1)
        self.assertEqual(data["fees"][0]["fixed_amount"], 5.0)
        self.assertEqual(len(data["taxes"]), 1)
        self.assertEqual(data["taxes"][0]["tax_amount"], 2.0)

    def test_create_full_bad_fk_rollback(self):
        count_before = len(self.conn.execute("SELECT id FROM transactions").fetchall())
        resp = client.post(
            "/api/v1/transactions/full",
            json={
                "transaction": {
                    "timestamp": "2024-06-01T10:00:00",
                    "type": "INVESTMENT_BUY",
                    "entity_id": 999,
                    "currency": "USD",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                },
                "fees": [
                    {
                        "fee_type": "BROKER",
                        "nature": "FIXED",
                        "currency": "USD",
                        "fixed_amount": 5.0,
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 400)
        count_after = len(self.conn.execute("SELECT id FROM transactions").fetchall())
        self.assertEqual(count_after, count_before, "No tx should exist after rollback")

    def test_create_full_tx_before_snapshot_reconciles(self):
        """No snapshot-date restriction: a buy before the latest snapshot reconciles
        via injected cash and a refreshed snapshot adjustment."""
        queries.create_balance_snapshot(
            self.conn,
            self.eid,
            "USD",
            5000.0,
            "2025-01-01T00:00:00",
        )
        resp = client.post(
            "/api/v1/transactions/full",
            json={
                "transaction": {
                    "timestamp": "2024-06-01T10:00:00",
                    "type": "INVESTMENT_BUY",
                    "entity_id": self.eid,
                    "currency": "USD",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                },
            },
        )
        self.assertEqual(resp.status_code, 201)

        inj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2024-05-31T23:59:59")
        self.assertIsNotNone(inj)
        assert inj is not None
        self.assertAlmostEqual(inj["total_value"], 500.0)

        snap = queries.get_latest_snapshot(self.conn, self.eid, "USD")
        assert snap is not None
        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", snap["id"])
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 5000.0)

    def test_create_full_tx_no_conflict_after_snapshot(self):
        queries.create_balance_snapshot(
            self.conn,
            self.eid,
            "USD",
            5000.0,
            "2025-01-01T00:00:00",
        )
        resp = client.post(
            "/api/v1/transactions/full",
            json={
                "transaction": {
                    "timestamp": "2025-06-01T10:00:00",
                    "type": "INVESTMENT_BUY",
                    "entity_id": self.eid,
                    "currency": "USD",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                },
            },
        )
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# Batch transaction tests
# ---------------------------------------------------------------------------


class TestBatchService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patchers = [
            patch("services.transaction_batch_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_batch_svc

        return transaction_batch_svc

    def import_tx_svc(self):
        from services import transaction_svc

        return transaction_svc

    def test_create_batch_one(self):
        svc = self.import_svc()
        body = BatchCreate(
            transactions=[
                TransactionCreate(
                    timestamp=datetime(2024, 6, 1, 10, 0, 0),
                    type=TransactionType.INVESTMENT_BUY,
                    entity_id=self.eid,
                    currency="USD",
                    quantity=10.0,
                    unit_price=50.0,
                ),
            ],
        )
        result = svc.create(body)
        self.assertEqual(len(result.transactions), 1)
        self.assertEqual(result.transactions[0].total_value, 500.0)

    def test_create_batch_multiple(self):
        svc = self.import_svc()
        body = BatchCreate(
            transactions=[
                TransactionCreate(
                    timestamp=datetime(2024, 6, 1, 10, 0, 0),
                    type=TransactionType.INCOME,
                    entity_id=self.eid,
                    currency="USD",
                    total_value=1000.0,
                ),
                TransactionCreate(
                    timestamp=datetime(2024, 6, 2, 10, 0, 0),
                    type=TransactionType.INVESTMENT_BUY,
                    entity_id=self.eid,
                    currency="USD",
                    quantity=5.0,
                    unit_price=100.0,
                ),
            ],
        )
        result = svc.create(body)
        self.assertEqual(len(result.transactions), 2)
        self.assertEqual(result.transactions[0].total_value, 1000.0)
        self.assertEqual(result.transactions[1].total_value, 500.0)

    def test_create_batch_rollback_on_bad_fk(self):
        svc = self.import_svc()
        tx_svc = self.import_tx_svc()
        body = BatchCreate(
            transactions=[
                TransactionCreate(
                    timestamp=datetime(2024, 6, 1, 10, 0, 0),
                    type=TransactionType.INCOME,
                    entity_id=self.eid,
                    currency="USD",
                    total_value=1000.0,
                ),
                TransactionCreate(
                    timestamp=datetime(2024, 6, 2, 10, 0, 0),
                    type=TransactionType.INVESTMENT_BUY,
                    entity_id=999,
                    currency="USD",
                    quantity=5.0,
                    unit_price=100.0,
                ),
            ],
        )
        with self.assertRaises(TxFKNotFound):
            svc.create(body)
        all_tx = tx_svc.list_all()
        self.assertEqual(len(all_tx), 0, "No tx should exist after rollback")


class TestBatchRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        seed_currency_pair(self.conn)
        self.patchers = [
            patch("services.transaction_batch_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def test_create_batch_one(self):
        resp = client.post(
            "/api/v1/transactions/batch",
            json={
                "transactions": [
                    {
                        "timestamp": "2024-06-01T10:00:00",
                        "type": "INVESTMENT_BUY",
                        "entity_id": self.eid,
                        "currency": "USD",
                        "quantity": 10.0,
                        "unit_price": 50.0,
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(len(data["transactions"]), 1)
        self.assertEqual(data["transactions"][0]["total_value"], 500.0)

    def test_create_batch_multiple(self):
        resp = client.post(
            "/api/v1/transactions/batch",
            json={
                "transactions": [
                    {
                        "timestamp": "2024-06-01T10:00:00",
                        "type": "INCOME",
                        "entity_id": self.eid,
                        "currency": "USD",
                        "total_value": 1000.0,
                    },
                    {
                        "timestamp": "2024-06-02T10:00:00",
                        "type": "INVESTMENT_BUY",
                        "entity_id": self.eid,
                        "currency": "USD",
                        "quantity": 5.0,
                        "unit_price": 100.0,
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(len(data["transactions"]), 2)

    def test_create_batch_empty(self):
        resp = client.post(
            "/api/v1/transactions/batch",
            json={
                "transactions": [],
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_batch_bad_fk(self):
        resp = client.post(
            "/api/v1/transactions/batch",
            json={
                "transactions": [
                    {
                        "timestamp": "2024-06-01T10:00:00",
                        "type": "INCOME",
                        "entity_id": 999,
                        "currency": "USD",
                        "total_value": 1000.0,
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 400)


class TestFxRateAutoResolve(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)  # USD self-rate
        seed_currency_pair(self.conn)  # EUR→USD
        queries.insert_rate(self.conn, "USD", "JPY", 150.0, datetime(2024, 1, 1, 0, 0, 0))
        queries.insert_rate(self.conn, "JPY", "JPY", 1.0, datetime(2024, 1, 1, 0, 0, 0))
        self.patcher = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.cur_patcher = patch("services.currency_svc.get_db", return_value=self.conn)
        self.cur_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.cur_patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_svc

        return transaction_svc

    def test_auto_resolves_fx_rate_when_null_and_currencies_differ(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            payment_currency="JPY",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=None,
        )
        result = svc.create(body)
        self.assertEqual(result.total_value, 500.0)
        self.assertEqual(result.fx_rate, 150.0)
        self.assertEqual(result.gross_amount, 75000.0)  # 500 * 150
        self.assertEqual(result.net_amount, 75000.0)

    def test_does_not_overwrite_user_provided_fx_rate(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            payment_currency="JPY",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=148.5,
        )
        result = svc.create(body)
        self.assertEqual(result.fx_rate, 148.5)
        self.assertAlmostEqual(result.gross_amount, 74250.0)

    def test_no_op_when_same_currency(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            payment_currency="USD",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=None,
        )
        result = svc.create(body)
        self.assertEqual(result.fx_rate, None)
        self.assertEqual(result.gross_amount, None)

    def test_no_op_when_no_payment_currency(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=1.1,
        )
        result = svc.create(body)
        self.assertEqual(result.fx_rate, 1.1)
        self.assertEqual(result.gross_amount, None)

    def test_update_re_resolves_when_fx_rate_cleared(self):
        svc = self.import_svc()
        body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            payment_currency="JPY",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=148.5,
        )
        created = svc.create(body)
        self.assertEqual(created.fx_rate, 148.5)

        update_body = svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            payment_currency="JPY",
            quantity=10.0,
            unit_price=50.0,
            fx_rate=None,
        )
        updated = svc.update(created.id, update_body)
        self.assertEqual(updated.fx_rate, 150.0)
        self.assertEqual(updated.gross_amount, 75000.0)


if __name__ == "__main__":
    unittest.main()
