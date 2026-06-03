import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import EntityType, FeeType, FeeNature, TransactionType
from routes.transaction_fees import router

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
        conn, timestamp="2024-06-01T10:00:00", type_="INVESTMENT_BUY",
        entity_id=eid, currency="USD", total_value=100.0,
    )


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestFeeQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_fees(self.conn), [])

    def test_create_returns_id(self):
        fid = queries.create_fee(
            self.conn, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD", fixed_amount=10.0,
        )
        self.assertIsInstance(fid, int)
        self.assertGreater(fid, 0)

    def test_get_returns_row(self):
        fid = queries.create_fee(
            self.conn, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD", fixed_amount=10.0,
        )
        row = queries.get_fee(self.conn, fid)
        self.assertIsNotNone(row)
        self.assertEqual(row["fee_type"], "BROKER")
        self.assertEqual(row["fixed_amount"], 10.0)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_fee(self.conn, 999))

    def test_get_by_transaction(self):
        fid = queries.create_fee(
            self.conn, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD", fixed_amount=5.0,
        )
        rows = queries.get_fees_by_transaction(self.conn, self.tx_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], fid)

    def test_update_returns_true(self):
        fid = queries.create_fee(
            self.conn, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD", fixed_amount=10.0,
        )
        ok = queries.update_fee(
            self.conn, fid, transaction_id=self.tx_id, fee_type="PLATFORM",
            nature="PERCENTAGE", currency="EUR", percentage=0.5,
        )
        self.assertTrue(ok)
        row = queries.get_fee(self.conn, fid)
        self.assertEqual(row["fee_type"], "PLATFORM")
        self.assertEqual(row["percentage"], 0.5)

    def test_update_nonexistent(self):
        ok = queries.update_fee(
            self.conn, 999, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD",
        )
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        fid = queries.create_fee(
            self.conn, transaction_id=self.tx_id, fee_type="BROKER",
            nature="FIXED", currency="USD", fixed_amount=10.0,
        )
        ok = queries.delete_fee(self.conn, fid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_fee(self.conn, fid))

    def test_delete_nonexistent(self):
        ok = queries.delete_fee(self.conn, 999)
        self.assertFalse(ok)


class TestFeeService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)
        self.patcher = patch("services.transaction_fee_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import transaction_fee_svc
        return transaction_fee_svc

    def test_create(self):
        svc = self.import_svc()
        body = svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD", fixed_amount=15.0,
        )
        result = svc.create(body)
        self.assertEqual(result.fee_type, FeeType.BROKER)
        self.assertEqual(result.fixed_amount, 15.0)
        self.assertIsNotNone(result.id)

    def test_create_missing_transaction(self):
        svc = self.import_svc()
        body = svc.TransactionFeeCreate(
            transaction_id=999, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD",
        )
        with self.assertRaises(svc.TransactionNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.PLATFORM,
            nature=FeeNature.PERCENTAGE, currency="USD", percentage=0.25,
        ))
        result = svc.get(created.id)
        self.assertEqual(result.id, created.id)

    def test_get_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionFeeNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_svc()
        svc.create(svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD", fixed_amount=5.0,
        ))
        self.assertEqual(len(svc.list_all()), 1)

    def test_list_by_transaction(self):
        svc = self.import_svc()
        svc.create(svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD", fixed_amount=5.0,
        ))
        rows = svc.list_all(transaction_id=self.tx_id)
        self.assertEqual(len(rows), 1)

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD", fixed_amount=5.0,
        ))
        result = svc.update(created.id, svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.PLATFORM,
            nature=FeeNature.PERCENTAGE, currency="EUR", percentage=0.3,
        ))
        self.assertEqual(result.fee_type, FeeType.PLATFORM)
        self.assertEqual(result.percentage, 0.3)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionFeeNotFound):
            svc.update(999, svc.TransactionFeeCreate(
                transaction_id=self.tx_id, fee_type=FeeType.BROKER,
                nature=FeeNature.FIXED, currency="USD",
            ))

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(svc.TransactionFeeCreate(
            transaction_id=self.tx_id, fee_type=FeeType.BROKER,
            nature=FeeNature.FIXED, currency="USD", fixed_amount=5.0,
        ))
        svc.delete(created.id)
        with self.assertRaises(svc.TransactionFeeNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.TransactionFeeNotFound):
            svc.delete(999)


class TestFeeRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.tx_id = seed_transaction(self.conn, self.eid)
        self.patcher = patch("services.transaction_fee_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/transaction-fees")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id,
            "fee_type": "BROKER",
            "nature": "FIXED",
            "currency": "USD",
            "fixed_amount": 12.5,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["fee_type"], "BROKER")
        self.assertEqual(data["fixed_amount"], 12.5)
        self.assertIn("id", data)

    def test_create_bad_transaction(self):
        resp = client.post("/api/v1/transaction-fees", json={
            "transaction_id": 999,
            "fee_type": "BROKER",
            "nature": "FIXED",
            "currency": "USD",
        })
        self.assertEqual(resp.status_code, 400)

    def test_get(self):
        create_resp = client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD", "fixed_amount": 5.0,
        })
        fid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/transaction-fees/{fid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], fid)

    def test_get_not_found(self):
        resp = client.get("/api/v1/transaction-fees/999")
        self.assertEqual(resp.status_code, 404)

    def test_list(self):
        client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD", "fixed_amount": 5.0,
        })
        resp = client.get("/api/v1/transaction-fees")
        self.assertEqual(len(resp.json()), 1)

    def test_list_filter_by_transaction(self):
        client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD", "fixed_amount": 5.0,
        })
        resp = client.get(f"/api/v1/transaction-fees?transaction_id={self.tx_id}")
        self.assertEqual(len(resp.json()), 1)

    def test_update(self):
        create_resp = client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD", "fixed_amount": 5.0,
        })
        fid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/transaction-fees/{fid}", json={
            "transaction_id": self.tx_id, "fee_type": "PLATFORM",
            "nature": "PERCENTAGE", "currency": "EUR", "percentage": 0.5,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["fee_type"], "PLATFORM")
        self.assertEqual(resp.json()["percentage"], 0.5)

    def test_update_not_found(self):
        resp = client.put("/api/v1/transaction-fees/999", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/transaction-fees", json={
            "transaction_id": self.tx_id, "fee_type": "BROKER",
            "nature": "FIXED", "currency": "USD", "fixed_amount": 5.0,
        })
        fid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/transaction-fees/{fid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/transaction-fees/{fid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/transaction-fees/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
