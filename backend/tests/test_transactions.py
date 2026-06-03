import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models import (
    FullTransactionCreate,
    FullTransactionResponse,
    TransactionCreate,
    TransactionFeeInner,
    TransactionTaxInner,
)
from models.enums import EntityType, FeeNature, FeeType, TransactionType
from routes.transactions import router
from services.transaction_svc import FKNotFound as TxFKNotFound

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
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
            entity_id=self.eid, currency="USD", total_value=500.0,
            quantity=10.0, unit_price=50.0,
            notes="test note",
        )
        self.assertIsInstance(tx_id, int)
        self.assertGreater(tx_id, 0)

    def test_get_returns_row(self):
        tx_id = queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00",             type_="INVESTMENT_SELL",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        row = queries.get_transaction(self.conn, tx_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["type"], "INVESTMENT_SELL")
        self.assertEqual(row["entity_id"], self.eid)
        self.assertEqual(row["total_value"], 100.0)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_transaction(self.conn, 999))

    def test_list_all(self):
        queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00",             type_="INVESTMENT_BUY",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        queries.create_transaction(
            self.conn, timestamp="2024-06-01T11:00:00", type_="INVESTMENT_SELL",
            entity_id=self.eid, currency="USD", total_value=200.0,
        )
        self.assertEqual(len(queries.get_all_transactions(self.conn)), 2)

    def test_list_by_entity(self):
        tx_id = queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00",             type_="INVESTMENT_BUY",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        rows = queries.get_transactions_by_entity(self.conn, self.eid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], tx_id)

    def test_list_by_entity_empty(self):
        self.assertEqual(queries.get_transactions_by_entity(self.conn, 999), [])

    def test_update_returns_true(self):
        tx_id = queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00",             type_="INVESTMENT_BUY",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        ok = queries.update_transaction(
            self.conn, tx_id, timestamp="2024-06-02T10:00:00", type_="INVESTMENT_SELL",
            entity_id=self.eid, currency="USD", total_value=200.0,
        )
        self.assertTrue(ok)
        row = queries.get_transaction(self.conn, tx_id)
        self.assertEqual(row["type"], "INVESTMENT_SELL")
        self.assertEqual(row["total_value"], 200.0)

    def test_update_nonexistent(self):
        ok = queries.update_transaction(
            self.conn, 999, timestamp="2024-06-01T10:00:00", type_="BUY",
            entity_id=self.eid, currency="USD",
        )
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        tx_id = queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00",             type_="INVESTMENT_BUY",
            entity_id=self.eid, currency="USD", total_value=100.0,
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
        svc.create(svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0), type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid, currency="USD",
        ))
        svc.create(svc.TransactionCreate(
            timestamp=datetime(2024, 6, 2, 10, 0, 0), type=TransactionType.INVESTMENT_SELL,
            entity_id=self.eid, currency="USD",
        ))
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0), type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid, currency="USD", quantity=10.0, unit_price=50.0,
        ))
        result = svc.update(created.id, svc.TransactionCreate(
            timestamp=datetime(2024, 6, 2, 10, 0, 0), type=TransactionType.INVESTMENT_SELL,
            entity_id=self.eid, currency="USD", quantity=5.0, unit_price=40.0,
            total_value=200.0,
        ))
        self.assertEqual(result.type, TransactionType.INVESTMENT_SELL)
        self.assertEqual(result.total_value, 200.0)
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.update(999, svc.TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0), type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid, currency="USD",
            ))

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionCreate(
            timestamp=datetime(2024, 6, 1, 10, 0, 0), type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid, currency="USD",
        ))
        svc.delete(created.id)
        with self.assertRaises(svc.TransactionNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionNotFound):
            svc.delete(999)

    def test_create_with_multiple_fks(self):
        queries.create_market_asset(
            self.conn, market_code="AAPL.US", currency_code="USD",
            asset_type="STOCK", ticker="AAPL",
        )
        pa_id = queries.create_portfolio_asset(
            self.conn, market_code="AAPL.US",
        )
        fe_id = queries.create_fiscal_exemption(
            self.conn, exemption_type="WITHHOLDING_TAX",
            description="US withholding", exemption_rate=0.15,
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
        resp = client.post("/api/v1/transactions", json={
            "timestamp": "2024-06-01T10:00:00",
            "type": "INVESTMENT_BUY",
            "entity_id": self.eid,
            "currency": "USD",
            "quantity": 10.0,
            "unit_price": 50.0,
            "notes": "test note",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["type"], "INVESTMENT_BUY")
        self.assertEqual(data["total_value"], 500.0)
        self.assertEqual(data["notes"], "test note")
        self.assertIn("id", data)

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
        client.post("/api/v1/transactions", json=default_tx_body(
            timestamp="2024-06-02T10:00:00", type="INVESTMENT_SELL",
        ))
        resp = client.get("/api/v1/transactions")
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        create_resp = client.post("/api/v1/transactions", json=default_tx_body())
        tx_id = create_resp.json()["id"]
        resp = client.put(f"/api/v1/transactions/{tx_id}", json={
            "timestamp": "2024-06-02T10:00:00",
            "type": "INVESTMENT_SELL",
            "entity_id": self.eid,
            "currency": "USD",
            "quantity": 5.0,
            "unit_price": 60.0,
            "total_value": 300.0,
        })
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
        resp = client.post("/api/v1/transactions/full", json={
            "transaction": {
                "timestamp": "2024-06-01T10:00:00",
                "type": "INVESTMENT_BUY",
                "entity_id": self.eid,
                "currency": "USD",
                "quantity": 10.0,
                "unit_price": 50.0,
            },
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["transaction"]["total_value"], 500.0)
        self.assertEqual(data["fees"], [])
        self.assertEqual(data["taxes"], [])

    def test_create_full_with_fees_and_taxes(self):
        resp = client.post("/api/v1/transactions/full", json={
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
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["transaction"]["notes"], "composite test")
        self.assertEqual(len(data["fees"]), 1)
        self.assertEqual(data["fees"][0]["fixed_amount"], 5.0)
        self.assertEqual(len(data["taxes"]), 1)
        self.assertEqual(data["taxes"][0]["tax_amount"], 2.0)

    def test_create_full_bad_fk_rollback(self):
        count_before = len(self.conn.execute(
            "SELECT id FROM transactions"
        ).fetchall())
        resp = client.post("/api/v1/transactions/full", json={
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
        })
        self.assertEqual(resp.status_code, 400)
        count_after = len(self.conn.execute(
            "SELECT id FROM transactions"
        ).fetchall())
        self.assertEqual(count_after, count_before, "No tx should exist after rollback")


if __name__ == "__main__":
    unittest.main()
