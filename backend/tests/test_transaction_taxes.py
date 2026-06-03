import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import EntityType, TransactionType
from routes.transaction_taxes import router

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


def seed_transaction(conn: sqlite3.Connection, eid: int) -> int:
    return queries.create_transaction(
        conn, timestamp="2024-06-01T10:00:00",         type_="INVESTMENT_SELL",
        entity_id=eid, currency="USD", total_value=1000.0,
    )


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestTaxQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_taxes(self.conn), [])

    def test_create_returns_id(self):
        tid = queries.create_tax(
            self.conn, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=150.0, currency="USD", tax_rate=0.15,
        )
        self.assertIsInstance(tid, int)
        self.assertGreater(tid, 0)

    def test_get_returns_row(self):
        tid = queries.create_tax(
            self.conn, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=150.0, currency="USD",
        )
        row = queries.get_tax(self.conn, tid)
        self.assertIsNotNone(row)
        self.assertEqual(row["tax_type"], "CAPITAL_GAINS")
        self.assertEqual(row["tax_amount"], 150.0)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_tax(self.conn, 999))

    def test_get_by_transaction(self):
        tid = queries.create_tax(
            self.conn, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=150.0, currency="USD",
        )
        rows = queries.get_taxes_by_transaction(self.conn, self.tx_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], tid)

    def test_update_returns_true(self):
        tid = queries.create_tax(
            self.conn, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        )
        ok = queries.update_tax(
            self.conn, tid, transaction_id=self.tx_id, tax_type="STAMP_DUTY",
            tax_amount=50.0, currency="EUR", tax_rate=0.005,
        )
        self.assertTrue(ok)
        row = queries.get_tax(self.conn, tid)
        self.assertEqual(row["tax_type"], "STAMP_DUTY")
        self.assertEqual(row["tax_amount"], 50.0)
        self.assertEqual(row["tax_rate"], 0.005)

    def test_update_nonexistent(self):
        ok = queries.update_tax(
            self.conn, 999, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        )
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        tid = queries.create_tax(
            self.conn, transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        )
        ok = queries.delete_tax(self.conn, tid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_tax(self.conn, tid))

    def test_delete_nonexistent(self):
        ok = queries.delete_tax(self.conn, 999)
        self.assertFalse(ok)


class TestTaxService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)
        self.patcher = patch("services.transaction_tax_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_tax_svc
        return transaction_tax_svc

    def test_create(self):
        svc = self.import_svc()
        body = svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=150.0, currency="USD", tax_rate=0.15,
        )
        result = svc.create(body)
        self.assertEqual(result.tax_type, "CAPITAL_GAINS")
        self.assertEqual(result.tax_amount, 150.0)
        self.assertEqual(result.tax_rate, 0.15)
        self.assertIsNotNone(result.id)

    def test_create_without_rate(self):
        svc = self.import_svc()
        body = svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="STAMP_DUTY",
            tax_amount=10.0, currency="GBP",
        )
        result = svc.create(body)
        self.assertIsNone(result.tax_rate)

    def test_create_missing_transaction(self):
        svc = self.import_svc()
        body = svc.TransactionTaxCreate(
            transaction_id=999, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        )
        with self.assertRaises(svc.TransactionNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        ))
        result = svc.get(created.id)
        self.assertEqual(result.id, created.id)

    def test_get_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionTaxNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_svc()
        svc.create(svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        ))
        self.assertEqual(len(svc.list_all()), 1)

    def test_list_by_transaction(self):
        svc = self.import_svc()
        svc.create(svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="STAMP_DUTY",
            tax_amount=5.0, currency="GBP",
        ))
        rows = svc.list_all(transaction_id=self.tx_id)
        self.assertEqual(len(rows), 1)

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        ))
        result = svc.update(created.id, svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="STAMP_DUTY",
            tax_amount=20.0, currency="GBP", tax_rate=0.005,
        ))
        self.assertEqual(result.tax_type, "STAMP_DUTY")
        self.assertEqual(result.tax_amount, 20.0)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionTaxNotFound):
            svc.update(999, svc.TransactionTaxCreate(
                transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
                tax_amount=100.0, currency="USD",
            ))

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionTaxCreate(
            transaction_id=self.tx_id, tax_type="CAPITAL_GAINS",
            tax_amount=100.0, currency="USD",
        ))
        svc.delete(created.id)
        with self.assertRaises(svc.TransactionTaxNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionTaxNotFound):
            svc.delete(999)


class TestTaxRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)
        self.patcher = patch("services.transaction_tax_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/transaction-taxes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id,
            "tax_type": "CAPITAL_GAINS",
            "tax_amount": 150.0,
            "currency": "USD",
            "tax_rate": 0.15,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["tax_type"], "CAPITAL_GAINS")
        self.assertEqual(data["tax_amount"], 150.0)
        self.assertIn("id", data)

    def test_create_bad_transaction(self):
        resp = client.post("/api/v1/transaction-taxes", json={
            "transaction_id": 999, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        self.assertEqual(resp.status_code, 400)

    def test_get(self):
        create_resp = client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        tid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/transaction-taxes/{tid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], tid)

    def test_get_not_found(self):
        resp = client.get("/api/v1/transaction-taxes/999")
        self.assertEqual(resp.status_code, 404)

    def test_list(self):
        client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        resp = client.get("/api/v1/transaction-taxes")
        self.assertEqual(len(resp.json()), 1)

    def test_list_filter_by_transaction(self):
        client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        resp = client.get(f"/api/v1/transaction-taxes?transaction_id={self.tx_id}")
        self.assertEqual(len(resp.json()), 1)

    def test_update(self):
        create_resp = client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        tid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/transaction-taxes/{tid}", json={
            "transaction_id": self.tx_id, "tax_type": "STAMP_DUTY",
            "tax_amount": 20.0, "currency": "GBP", "tax_rate": 0.005,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tax_type"], "STAMP_DUTY")

    def test_update_not_found(self):
        resp = client.put("/api/v1/transaction-taxes/999", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/transaction-taxes", json={
            "transaction_id": self.tx_id, "tax_type": "CAPITAL_GAINS",
            "tax_amount": 100.0, "currency": "USD",
        })
        tid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/transaction-taxes/{tid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/transaction-taxes/{tid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/transaction-taxes/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
