import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import EntityType, PeriodicityType
from routes.balance_snapshots import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_currency(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "USD", "USD", 1.0, datetime(2024, 1, 1, 0, 0, 0))


def seed_entity(conn: sqlite3.Connection) -> int:
    return queries.create_entity(conn, "Test Broker", EntityType.BROKER)


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


class TestBalanceSnapshotQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_balance_snapshots(self.conn), [])

    def test_create_returns_id(self):
        sid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 5000.0, "2025-01-01T00:00:00")
        self.assertIsInstance(sid, int)
        self.assertGreater(sid, 0)

    def test_get_returns_row(self):
        sid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 5000.0, "2025-01-01T00:00:00")
        row = queries.get_balance_snapshot(self.conn, sid)
        self.assertIsNotNone(row)
        self.assertEqual(row["entity_id"], self.eid)
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["amount"], 5000.0)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_balance_snapshot(self.conn, 999))

    def test_get_all_returns_all(self):
        queries.create_balance_snapshot(self.conn, self.eid, "USD", 1000.0, "2025-01-01T00:00:00")
        queries.create_balance_snapshot(self.conn, self.eid, "USD", 2000.0, "2025-06-01T00:00:00")
        all_items = queries.get_all_balance_snapshots(self.conn)
        self.assertEqual(len(all_items), 2)

    def test_get_latest_snapshot(self):
        queries.create_balance_snapshot(self.conn, self.eid, "USD", 1000.0, "2025-01-01T00:00:00")
        sid2 = queries.create_balance_snapshot(self.conn, self.eid, "USD", 2000.0, "2025-06-01T00:00:00")
        latest = queries.get_latest_snapshot(self.conn, self.eid, "USD")
        self.assertEqual(latest["id"], sid2)
        self.assertEqual(latest["amount"], 2000.0)

    def test_get_latest_snapshot_nonexistent_pair(self):
        self.assertIsNone(queries.get_latest_snapshot(self.conn, 999, "EUR"))

    def test_update_returns_true(self):
        sid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 5000.0, "2025-01-01T00:00:00")
        ok = queries.update_balance_snapshot(self.conn, sid, self.eid, "USD", 6000.0, "2025-06-01T00:00:00")
        self.assertTrue(ok)
        row = queries.get_balance_snapshot(self.conn, sid)
        self.assertEqual(row["amount"], 6000.0)

    def test_update_nonexistent(self):
        ok = queries.update_balance_snapshot(self.conn, 999, 1, "USD", 100.0, "2025-01-01T00:00:00")
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        sid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 5000.0, "2025-01-01T00:00:00")
        ok = queries.delete_balance_snapshot(self.conn, sid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_balance_snapshot(self.conn, sid))

    def test_delete_nonexistent(self):
        ok = queries.delete_balance_snapshot(self.conn, 999)
        self.assertFalse(ok)

    def test_has_transactions_on_or_after_returns_true(self):
        queries.create_transaction(
            self.conn, timestamp="2025-06-01T10:00:00", type_="MONEY_IN",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        result = queries.has_transactions_on_or_after(self.conn, self.eid, "USD", "2025-01-01T00:00:00")
        self.assertTrue(result)

    def test_has_transactions_on_or_after_returns_false(self):
        queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00", type_="MONEY_IN",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        result = queries.has_transactions_on_or_after(self.conn, self.eid, "USD", "2025-01-01T00:00:00")
        self.assertFalse(result)

    def test_has_schedules_on_or_before_returns_true(self):
        queries.create_schedule(
            self.conn, description="Test", start_date="2025-01-01",
            periodicity_type="MONTHLY",
            entity_id=self.eid, currency="USD",
        )
        result = queries.has_schedules_on_or_before(self.conn, self.eid, "USD", "2025-06-01")
        self.assertTrue(result)

    def test_has_schedules_on_or_before_returns_false(self):
        result = queries.has_schedules_on_or_before(self.conn, self.eid, "USD", "2025-06-01")
        self.assertFalse(result)


class TestBalanceSnapshotService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.patcher = patch("services.balance_snapshot_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import balance_snapshot_svc
        return balance_snapshot_svc

    def test_create_minimal(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        result = svc.create(body)
        self.assertEqual(result.entity_id, self.eid)
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.amount, 5000.0)
        self.assertIsNotNone(result.id)

    def test_create_with_notes(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1), notes="Initial balance",
        )
        result = svc.create(body)
        self.assertEqual(result.notes, "Initial balance")

    def test_create_entity_not_found(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=999, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        with self.assertRaises(svc.EntityNotFound):
            svc.create(body)

    def test_create_currency_not_found(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="XXX", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        with self.assertRaises(svc.CurrencyNotFound):
            svc.create(body)

    def test_create_conflict_with_transaction(self):
        queries.create_transaction(
            self.conn, timestamp="2025-06-15T10:00:00", type_="MONEY_IN",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 6, 1),
        )
        with self.assertRaises(svc.BalanceSnapshotConflict):
            svc.create(body)

    def test_create_no_conflict_with_older_transaction(self):
        queries.create_transaction(
            self.conn, timestamp="2024-06-01T10:00:00", type_="MONEY_IN",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        result = svc.create(body)
        self.assertIsNotNone(result.id)

    def test_create_conflict_with_schedule(self):
        queries.create_schedule(
            self.conn, description="Test", start_date="2025-01-01",
            periodicity_type="MONTHLY",
            entity_id=self.eid, currency="USD",
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 6, 1),
        )
        with self.assertRaises(svc.BalanceSnapshotConflict):
            svc.create(body)

    def test_get(self):
        svc = self.import_svc()
        created = svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        ))
        result = svc.get(created.id)
        self.assertEqual(result.amount, 5000.0)

    def test_get_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_svc()
        svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=1000.0,
            timestamp=datetime(2025, 1, 1),
        ))
        svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=2000.0,
            timestamp=datetime(2025, 6, 1),
        ))
        result = svc.list_all()
        self.assertEqual(len(result), 2)

    def test_list_all_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.list_all(), [])

    def test_list_all_filtered_by_entity(self):
        svc = self.import_svc()
        svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=1000.0,
            timestamp=datetime(2025, 1, 1),
        ))
        result = svc.list_all(entity_id=self.eid)
        self.assertEqual(len(result), 1)

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        ))
        result = svc.update(created.id, svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=6000.0,
            timestamp=datetime(2025, 6, 1),
        ))
        self.assertEqual(result.amount, 6000.0)
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.update(999, svc.BalanceSnapshotCreate(
                entity_id=self.eid, currency="USD", amount=100.0,
                timestamp=datetime(2025, 1, 1),
            ))

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(svc.BalanceSnapshotCreate(
            entity_id=self.eid, currency="USD", amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        ))
        svc.delete(created.id)
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.delete(999)


class TestBalanceSnapshotRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.patcher = patch("services.balance_snapshot_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/balance-snapshots")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create_minimal(self):
        resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid,
            "currency": "USD",
            "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["amount"], 5000.0)
        self.assertEqual(data["entity_id"], self.eid)
        self.assertIn("id", data)

    def test_create_with_notes(self):
        resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid,
            "currency": "USD",
            "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
            "notes": "Initial balance",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["notes"], "Initial balance")

    def test_create_entity_not_found(self):
        resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": 999,
            "currency": "USD",
            "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 404)

    def test_create_currency_not_found(self):
        resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid,
            "currency": "XXX",
            "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 404)

    def test_create_conflict_with_transaction(self):
        queries.create_transaction(
            self.conn, timestamp="2025-06-15T10:00:00", type_="MONEY_IN",
            entity_id=self.eid, currency="USD", total_value=100.0,
        )
        resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid,
            "currency": "USD",
            "amount": 5000.0,
            "timestamp": "2025-06-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 409)

    def test_get_snapshot(self):
        create_resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid,
            "currency": "USD",
            "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        sid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["amount"], 5000.0)

    def test_get_not_found(self):
        resp = client.get("/api/v1/balance-snapshots/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid, "currency": "USD", "amount": 1000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid, "currency": "USD", "amount": 2000.0,
            "timestamp": "2025-06-01T00:00:00",
        })
        resp = client.get("/api/v1/balance-snapshots")
        self.assertEqual(len(resp.json()), 2)

    def test_list_filter_by_entity(self):
        client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid, "currency": "USD", "amount": 1000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        resp = client.get(f"/api/v1/balance-snapshots?entity_id={self.eid}")
        self.assertEqual(len(resp.json()), 1)

    def test_update(self):
        create_resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid, "currency": "USD", "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        sid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/balance-snapshots/{sid}", json={
            "entity_id": self.eid, "currency": "USD", "amount": 6000.0,
            "timestamp": "2025-06-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["amount"], 6000.0)

    def test_update_not_found(self):
        resp = client.put("/api/v1/balance-snapshots/999", json={
            "entity_id": self.eid, "currency": "USD", "amount": 100.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/balance-snapshots", json={
            "entity_id": self.eid, "currency": "USD", "amount": 5000.0,
            "timestamp": "2025-01-01T00:00:00",
        })
        sid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/balance-snapshots/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
