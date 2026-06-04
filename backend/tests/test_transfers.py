import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models import TransactionFeeInner
from models.enums import EntityType
from routes.transfers import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_entity(conn: sqlite3.Connection, name: str = "Test Broker") -> int:
    return queries.create_entity(conn, name, EntityType.BROKER)


def seed_currency(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "USD", "USD", 1.0, datetime(2024, 1, 1, 0, 0, 0))


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestTransferService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.from_eid = seed_entity(self.conn, "Source Entity")
        self.to_eid = seed_entity(self.conn, "Dest Entity")
        seed_currency(self.conn)
        self.patchers = [
            patch("services.transfer_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.transaction_fee_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def import_svc(self):
        from services import transfer_svc
        return transfer_svc

    def import_tx_svc(self):
        from services import transaction_svc
        return transaction_svc

    def test_create_transfer_no_fees(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=self.from_eid,
            to_entity_id=self.to_eid,
            amount=1000.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
        )
        result = svc.create(body)
        self.assertEqual(result.from_transaction.type.value, "MONEY_OUT")
        self.assertEqual(result.from_transaction.entity_id, self.from_eid)
        self.assertEqual(result.from_transaction.total_value, 1000.0)
        self.assertEqual(result.to_transaction.type.value, "MONEY_IN")
        self.assertEqual(result.to_transaction.entity_id, self.to_eid)
        self.assertEqual(result.to_transaction.total_value, 1000.0)
        self.assertEqual(result.fees, [])

    def test_create_transfer_with_fees(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=self.from_eid,
            to_entity_id=self.to_eid,
            amount=500.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            fees=[
                TransactionFeeInner(
                    fee_type="BROKER",
                    nature="FIXED",
                    currency="USD",
                    fixed_amount=2.50,
                ),
            ],
        )
        result = svc.create(body)
        self.assertEqual(len(result.fees), 1)
        self.assertEqual(result.fees[0].fixed_amount, 2.50)
        self.assertEqual(result.fees[0].transaction_id, result.from_transaction.id)

    def test_create_from_entity_not_found(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=999,
            to_entity_id=self.to_eid,
            amount=100.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)

    def test_create_to_entity_not_found(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=self.from_eid,
            to_entity_id=999,
            amount=100.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)

    def test_create_currency_not_found(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=self.from_eid,
            to_entity_id=self.to_eid,
            amount=100.0,
            currency="XXX",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)

    def test_create_with_notes(self):
        svc = self.import_svc()
        body = svc.TransferCreate(
            from_entity_id=self.from_eid,
            to_entity_id=self.to_eid,
            amount=250.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
            notes="Monthly transfer",
        )
        result = svc.create(body)
        self.assertEqual(result.from_transaction.notes, "Monthly transfer")
        self.assertEqual(result.to_transaction.notes, "Monthly transfer")

    def test_atomic_rollback_on_bad_fk(self):
        svc = self.import_svc()
        tx_svc = self.import_tx_svc()
        body = svc.TransferCreate(
            from_entity_id=999,
            to_entity_id=self.to_eid,
            amount=100.0,
            currency="USD",
            timestamp=datetime(2024, 6, 1, 10, 0, 0),
        )
        with self.assertRaises(svc.FKNotFound):
            svc.create(body)
        all_tx = tx_svc.list_all()
        self.assertEqual(len(all_tx), 0, "No transactions should exist after rollback")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestTransferRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.from_eid = seed_entity(self.conn, "Source Entity")
        self.to_eid = seed_entity(self.conn, "Dest Entity")
        seed_currency(self.conn)
        self.patchers = [
            patch("services.transfer_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.transaction_fee_svc.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def test_create_transfer_no_fees(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.to_eid,
            "amount": 1000.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["from_transaction"]["type"], "MONEY_OUT")
        self.assertEqual(data["from_transaction"]["entity_id"], self.from_eid)
        self.assertEqual(data["to_transaction"]["type"], "MONEY_IN")
        self.assertEqual(data["to_transaction"]["entity_id"], self.to_eid)
        self.assertEqual(data["fees"], [])

    def test_create_transfer_with_fees(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.to_eid,
            "amount": 500.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
            "fees": [
                {
                    "fee_type": "BROKER",
                    "nature": "FIXED",
                    "currency": "USD",
                    "fixed_amount": 2.50,
                },
            ],
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(len(data["fees"]), 1)
        self.assertEqual(data["fees"][0]["fixed_amount"], 2.50)

    def test_create_from_entity_not_found(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": 999,
            "to_entity_id": self.to_eid,
            "amount": 100.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_to_entity_not_found(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": 999,
            "amount": 100.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_currency_not_found(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.to_eid,
            "amount": 100.0,
            "currency": "XXX",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_negative_amount(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.to_eid,
            "amount": -100.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 422)

    def test_create_same_entity(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.from_eid,
            "amount": 100.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
        })
        self.assertEqual(resp.status_code, 422)

    def test_create_with_notes(self):
        resp = client.post("/api/v1/transfers", json={
            "from_entity_id": self.from_eid,
            "to_entity_id": self.to_eid,
            "amount": 250.0,
            "currency": "USD",
            "timestamp": "2024-06-01T10:00:00",
            "notes": "Monthly transfer",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["from_transaction"]["notes"], "Monthly transfer")
        self.assertEqual(data["to_transaction"]["notes"], "Monthly transfer")


if __name__ == "__main__":
    unittest.main()
