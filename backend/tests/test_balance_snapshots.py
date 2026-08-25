import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import EntityType
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
        assert row is not None
        assert row is not None
        assert row is not None
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
        assert latest is not None
        self.assertEqual(latest["id"], sid2)
        self.assertEqual(latest["amount"], 2000.0)

    def test_get_latest_snapshot_nonexistent_pair(self):
        self.assertIsNone(queries.get_latest_snapshot(self.conn, 999, "EUR"))

    def test_update_returns_true(self):
        sid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 5000.0, "2025-01-01T00:00:00")
        ok = queries.update_balance_snapshot(self.conn, sid, self.eid, "USD", 6000.0, "2025-06-01T00:00:00")
        self.assertTrue(ok)
        row = queries.get_balance_snapshot(self.conn, sid)
        assert row is not None
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
            self.conn,
            timestamp="2025-06-01T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        result = queries.has_transactions_on_or_after(self.conn, self.eid, "USD", "2025-01-01T00:00:00")
        self.assertTrue(result)

    def test_has_transactions_on_or_after_returns_false(self):
        queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        result = queries.has_transactions_on_or_after(self.conn, self.eid, "USD", "2025-01-01T00:00:00")
        self.assertFalse(result)

    def test_has_schedules_on_or_before_returns_true(self):
        queries.create_schedule(
            self.conn,
            description="Test",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
            entity_id=self.eid,
            currency="USD",
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
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
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
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp=datetime(2025, 1, 1),
            notes="Initial balance",
        )
        result = svc.create(body)
        self.assertEqual(result.notes, "Initial balance")

    def test_create_entity_not_found(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=999,
            currency="USD",
            amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        with self.assertRaises(svc.EntityNotFound):
            svc.create(body)

    def test_create_currency_not_found(self):
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid,
            currency="XXX",
            amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        with self.assertRaises(svc.CurrencyNotFound):
            svc.create(body)

    def test_create_conflict_with_transaction(self):
        queries.create_transaction(
            self.conn,
            timestamp="2025-06-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp=datetime(2025, 6, 1),
        )
        with self.assertRaises(svc.BalanceSnapshotConflict):
            svc.create(body)

    def test_create_no_conflict_with_older_transaction(self):
        queries.create_transaction(
            self.conn,
            timestamp="2024-06-01T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp=datetime(2025, 1, 1),
        )
        result = svc.create(body)
        self.assertIsNotNone(result.id)

    def test_create_conflict_with_schedule(self):
        queries.create_schedule(
            self.conn,
            description="Test",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
            entity_id=self.eid,
            currency="USD",
        )
        svc = self.import_svc()
        body = svc.BalanceSnapshotCreate(
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp=datetime(2025, 6, 1),
        )
        with self.assertRaises(svc.BalanceSnapshotConflict):
            svc.create(body)

    def test_get(self):
        svc = self.import_svc()
        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=5000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )
        result = svc.get(created.id)
        self.assertEqual(result.amount, 5000.0)

    def test_get_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )
        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=2000.0,
                timestamp=datetime(2025, 6, 1),
            )
        )
        result = svc.list_all()
        self.assertEqual(len(result), 2)

    def test_list_all_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.list_all(), [])

    def test_list_all_filtered_by_entity(self):
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )
        result = svc.list_all(entity_id=self.eid)
        self.assertEqual(len(result), 1)

    def test_update(self):
        svc = self.import_svc()
        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=5000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )
        result = svc.update(
            created.id,
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=6000.0,
                timestamp=datetime(2025, 6, 1),
            ),
        )
        self.assertEqual(result.amount, 6000.0)
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_svc()
        with self.assertRaises(svc.BalanceSnapshotNotFound):
            svc.update(
                999,
                svc.BalanceSnapshotCreate(
                    entity_id=self.eid,
                    currency="USD",
                    amount=100.0,
                    timestamp=datetime(2025, 1, 1),
                ),
            )

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=5000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )
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
        resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["amount"], 5000.0)
        self.assertEqual(data["entity_id"], self.eid)
        self.assertIn("id", data)

    def test_create_with_notes(self):
        resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
                "notes": "Initial balance",
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["notes"], "Initial balance")

    def test_create_entity_not_found(self):
        resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": 999,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_currency_not_found(self):
        resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "XXX",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_conflict_with_transaction(self):
        queries.create_transaction(
            self.conn,
            timestamp="2025-06-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=100.0,
        )
        resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-06-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 409)

    def test_get_snapshot(self):
        create_resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        sid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["amount"], 5000.0)

    def test_get_not_found(self):
        resp = client.get("/api/v1/balance-snapshots/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 1000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 2000.0,
                "timestamp": "2025-06-01T00:00:00",
            },
        )
        resp = client.get("/api/v1/balance-snapshots")
        self.assertEqual(len(resp.json()), 2)

    def test_list_filter_by_entity(self):
        client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 1000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        resp = client.get(f"/api/v1/balance-snapshots?entity_id={self.eid}")
        self.assertEqual(len(resp.json()), 1)

    def test_update(self):
        create_resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        sid = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/balance-snapshots/{sid}",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 6000.0,
                "timestamp": "2025-06-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["amount"], 6000.0)

    def test_update_not_found(self):
        resp = client.put(
            "/api/v1/balance-snapshots/999",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 100.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post(
            "/api/v1/balance-snapshots",
            json={
                "entity_id": self.eid,
                "currency": "USD",
                "amount": 5000.0,
                "timestamp": "2025-01-01T00:00:00",
            },
        )
        sid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/balance-snapshots/{sid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/balance-snapshots/999")
        self.assertEqual(resp.status_code, 404)


class TestBalanceSnapshotAdjustments(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)
        self.patcher = patch("services.balance_snapshot_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.patcher2 = patch("services.transaction_svc.get_db", return_value=self.conn)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        self.conn.close()

    def import_svc(self):
        from services import balance_snapshot_svc

        return balance_snapshot_svc

    def test_first_snapshot_has_adjustment(self):
        svc = self.import_svc()
        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10000.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        # first snapshot: computed = 0 (no prior transactions) → adjustment = amount
        self.assertAlmostEqual(adj["total_value"], 10000.0, places=2)
        self.assertEqual(adj["timestamp"], "2025-01-09T23:59:59")

    def test_first_snapshot_reconciles_prior_transactions(self):
        svc = self.import_svc()
        queries.create_transaction(
            self.conn,
            timestamp="2025-01-05T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=1000.0,
        )
        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=500.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        # computed = 1000 (prior income) → adjustment = 500 - 1000 = -500
        self.assertAlmostEqual(adj["total_value"], -500.0, places=2)

        # continuity: actual balance at the snapshot date lands on the target
        balance = queries.get_balance_at_date(self.conn, self.eid, "USD", "2025-01-10T00:00:00")
        self.assertAlmostEqual(balance, 500.0, places=2)

    def test_snapshot_with_adjustment(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        self.assertIsNotNone(adj)
        self.assertAlmostEqual(adj["total_value"], -49.0, places=2)

    def test_adjustment_recalculation(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj_before = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_before is not None
        self.assertAlmostEqual(adj_before["total_value"], -49.0, places=2)

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-11T10:00:00",
            type_="MONEY_OUT",
            entity_id=self.eid,
            currency="USD",
            total_value=5.0,
        )

        from services.transaction_svc import _recalculate_adjustments

        _recalculate_adjustments(self.conn, self.eid, "USD", "2025-01-11T10:00:00")

        adj_after = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_after is not None
        self.assertAlmostEqual(adj_after["total_value"], -44.0, places=2)

    def test_delete_snapshot_removes_adjustment(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        self.assertIsNotNone(adj)

        svc.delete(created.id)

        adj_after = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        self.assertIsNone(adj_after)

    def test_update_snapshot_recalculates_adjustment(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj_before = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_before is not None
        self.assertAlmostEqual(adj_before["total_value"], -49.0, places=2)

        svc.update(
            created.id,
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=20.0,
                timestamp=datetime(2025, 1, 18),
            ),
        )

        adj_after = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_after is not None
        self.assertAlmostEqual(adj_after["total_value"], -40.0, places=2)

    def test_balance_at_date(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )

        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=500.0,
        )

        balance = queries.get_balance_at_date(self.conn, self.eid, "USD", "2025-01-20T00:00:00")
        self.assertAlmostEqual(balance, 1500.0, places=2)

    def test_actual_balance_includes_adjustment(self):
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=10.0, timestamp=datetime(2025, 1, 10))
        )
        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )
        created = svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=11.0, timestamp=datetime(2025, 1, 18))
        )
        # adjustment = 11 - (10 + 50) = -49; actual balance at the snapshot date
        # must land on the target (11), not the raw ledger sum (60).
        balance = queries.get_balance_at_date(self.conn, self.eid, "USD", "2025-01-18T00:00:00")
        self.assertAlmostEqual(balance, 11.0, places=2)
        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        self.assertEqual(adj["balance_snapshot_id"], created.id)

    def test_computed_balance_excludes_own_adjustment(self):
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=10.0, timestamp=datetime(2025, 1, 10))
        )
        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )
        created = svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=11.0, timestamp=datetime(2025, 1, 18))
        )
        actual = queries.get_balance_at_date(self.conn, self.eid, "USD", "2025-01-18T00:00:00")
        computed = queries.get_balance_at_date(
            self.conn, self.eid, "USD", "2025-01-18T00:00:00", exclude_adjustment_snapshot_id=created.id
        )
        self.assertAlmostEqual(actual, 11.0, places=2)
        self.assertAlmostEqual(computed, 60.0, places=2)

    def test_computed_excludes_only_own_adjustment_not_injected(self):
        """Regression (SQL NULL semantics): excluding the snapshot's own adjustment
        must not silently drop standalone injected adjustments (balance_snapshot_id NULL)."""
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=10.0, timestamp=datetime(2025, 1, 10))
        )
        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )
        queries.create_adjustment_transaction(
            self.conn, self.eid, "USD", 25.0, "2025-01-16T23:59:59", None, "Inferred cash for investment purchases"
        )
        created = svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=11.0, timestamp=datetime(2025, 1, 18))
        )
        computed = queries.get_balance_at_date(
            self.conn, self.eid, "USD", "2025-01-18T00:00:00", exclude_adjustment_snapshot_id=created.id
        )
        # 10 + 50 income + 25 injected = 85; only the snapshot's own adjustment is excluded
        self.assertAlmostEqual(computed, 85.0, places=2)

    def test_adjustment_placed_day_before_snapshot(self):
        svc = self.import_svc()
        svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=10.0, timestamp=datetime(2025, 1, 10))
        )
        queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )
        created = svc.create(
            svc.BalanceSnapshotCreate(entity_id=self.eid, currency="USD", amount=11.0, timestamp=datetime(2025, 1, 18))
        )
        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        self.assertEqual(adj["timestamp"], "2025-01-17T23:59:59")

    def test_multiple_snapshots_same_entity(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=2000.0,
                timestamp=datetime(2025, 6, 1),
            )
        )

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=3000.0,
                timestamp=datetime(2025, 12, 1),
            )
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 3)

    def test_no_transactions_between_snapshots(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=2000.0,
                timestamp=datetime(2025, 6, 1),
            )
        )

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        self.assertIsNotNone(adj)
        self.assertAlmostEqual(adj["total_value"], 1000.0, places=2)

    def test_snapshot_before_existing_snapshot(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=2000.0,
                timestamp=datetime(2025, 6, 1),
            )
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=1000.0,
                timestamp=datetime(2025, 1, 1),
            )
        )

        # Every snapshot has its own adjustment, including the earlier one
        # (which is now the earliest). computed = 0 → adjustment = 1000.
        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 1000.0, places=2)

    def test_delete_transaction_between_snapshots(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        tx = queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj_before = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_before is not None
        self.assertAlmostEqual(adj_before["total_value"], -49.0, places=2)

        queries.delete_transaction(self.conn, tx)

        from services.transaction_svc import _recalculate_adjustments

        _recalculate_adjustments(self.conn, self.eid, "USD", "2025-01-15T10:00:00")

        adj_after = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_after is not None
        self.assertAlmostEqual(adj_after["total_value"], 1.0, places=2)

    def test_update_transaction_amount(self):
        svc = self.import_svc()

        svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=10.0,
                timestamp=datetime(2025, 1, 10),
            )
        )

        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=50.0,
        )

        created = svc.create(
            svc.BalanceSnapshotCreate(
                entity_id=self.eid,
                currency="USD",
                amount=11.0,
                timestamp=datetime(2025, 1, 18),
            )
        )

        adj_before = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_before is not None
        self.assertAlmostEqual(adj_before["total_value"], -49.0, places=2)

        queries.update_transaction(
            self.conn,
            tx_id,
            timestamp="2025-01-15T10:00:00",
            type_="INCOME",
            entity_id=self.eid,
            currency="USD",
            total_value=60.0,
        )

        from services.transaction_svc import _recalculate_adjustments

        _recalculate_adjustments(self.conn, self.eid, "USD", "2025-01-15T10:00:00")

        adj_after = queries.get_adjustment_transaction(self.conn, self.eid, "USD", created.id)
        assert adj_after is not None
        self.assertAlmostEqual(adj_after["total_value"], -59.0, places=2)


class TestCreateTransactionBeforeExistingSnapshot(unittest.TestCase):
    """Regression: creating a INCOME in the past when a balance snapshot
    already exists should not raise IntegrityError (CHECK constraint)"""

    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)

    def test_create_money_in_before_existing_snapshot(self):
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        sid = queries.create_balance_snapshot(
            self.conn,
            entity_id=self.eid,
            currency="USD",
            amount=500.0,
            timestamp="2025-06-01T00:00:00",
        )

        body = TransactionCreate(
            timestamp=datetime(2025, 5, 25),
            type=TransactionType.INCOME,
            entity_id=self.eid,
            currency="USD",
            total_value=1000.0,
        )
        resp = create_tx(body, conn=self.conn)
        self.assertIsNotNone(resp.id)
        self.assertEqual(resp.type, TransactionType.INCOME)

        adj = queries.get_adjustment_transaction(self.conn, self.eid, "USD", sid)
        assert adj is not None
        self.assertIsNotNone(adj)
        self.assertAlmostEqual(adj["total_value"], -500.0, places=2)

    def test_create_money_in_before_no_snapshot(self):
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        body = TransactionCreate(
            timestamp=datetime(2025, 5, 25),
            type=TransactionType.INCOME,
            entity_id=self.eid,
            currency="USD",
            total_value=200.0,
        )
        resp = create_tx(body, conn=self.conn)
        self.assertIsNotNone(resp.id)


class TestAutoSnapshotOnFirstBuy(unittest.TestCase):
    """Regression: first INVESTMENT_BUY for an entity+currency pair with no
    prior snapshots or INCOME should inject inferred cash (standalone
    BALANCE_ADJUSTMENT) so the buy does not drive the pair negative."""

    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        queries.create_market_asset(
            self.conn,
            market_code="IWDA.AMS",
            currency_code="USD",
            asset_type="ETF",
            ticker="IWDA",
        )
        self.pa_id = queries.create_portfolio_asset(
            self.conn,
            market_code="IWDA.AMS",
        )

    def _adjustment_count(self):
        return self.conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE type = 'BALANCE_ADJUSTMENT'").fetchone()[
            "c"
        ]

    def test_first_buy_creates_snapshot(self):
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        body = TransactionCreate(
            timestamp=datetime(2025, 2, 19, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            total_value=90000.0,
            portfolio_asset_id=self.pa_id,
            quantity=50,
            unit_price=1800.0,
        )
        resp = create_tx(body, conn=self.conn)
        self.assertIsNotNone(resp.id)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 0)

        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-02-18T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 90000.0, places=2)
        self.assertIsNone(adj["balance_snapshot_id"])
        self.assertEqual(self._adjustment_count(), 1)

    def test_snapshot_anchors_cash_correctly(self):
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        body = TransactionCreate(
            timestamp=datetime(2025, 2, 19, 10, 0, 0),
            type=TransactionType.INVESTMENT_BUY,
            entity_id=self.eid,
            currency="USD",
            total_value=90000.0,
            portfolio_asset_id=self.pa_id,
            quantity=50,
            unit_price=1800.0,
        )
        create_tx(body, conn=self.conn)

        from db.queries import get_balance_at_date

        cash_after = get_balance_at_date(self.conn, self.eid, "USD", "2025-02-19T23:59:59")
        self.assertAlmostEqual(cash_after, 0.0, places=2)

    def test_no_snapshot_if_sufficient_cash_from_money_in(self):
        """Money deposited before a buy covers it fully → no injection needed."""
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 10, 10, 0, 0),
                type=TransactionType.INCOME,
                entity_id=self.eid,
                currency="USD",
                total_value=90000.0,
            ),
            conn=self.conn,
        )

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 19, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                total_value=90000.0,
                portfolio_asset_id=self.pa_id,
                quantity=50,
                unit_price=1800.0,
            ),
            conn=self.conn,
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 0)
        self.assertEqual(self._adjustment_count(), 0)

    def test_injects_shortfall_if_cash_insufficient(self):
        """Money deposited covers only part of the buy → injection for the shortfall."""
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 10, 10, 0, 0),
                type=TransactionType.INCOME,
                entity_id=self.eid,
                currency="USD",
                total_value=50000.0,
            ),
            conn=self.conn,
        )

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 19, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                total_value=90000.0,
                portfolio_asset_id=self.pa_id,
                quantity=50,
                unit_price=1800.0,
            ),
            conn=self.conn,
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 0)

        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-02-18T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 40000.0, places=2)
        self.assertEqual(self._adjustment_count(), 1)

    def test_prior_snapshot_debits_instead_of_injecting(self):
        """Prior snapshot anchors the pair → shortfall debits the balance (no injection)."""
        from db.queries import get_balance_at_date
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        queries.create_balance_snapshot(
            self.conn,
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp="2025-02-18T00:00:00",
        )

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 19, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                total_value=90000.0,
                portfolio_asset_id=self.pa_id,
                quantity=50,
                unit_price=1800.0,
            ),
            conn=self.conn,
        )

        self.assertEqual(self._adjustment_count(), 0)
        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)

        balance_after = get_balance_at_date(self.conn, self.eid, "USD", "2025-02-19T23:59:59")
        self.assertAlmostEqual(balance_after, -85000.0, places=2)

    def test_same_day_buys_merge_into_single_injection(self):
        """Multiple unfunded buys on the same date share one injected adjustment."""
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        for ts, value in ((datetime(2025, 2, 19, 9, 0, 0), 100.0), (datetime(2025, 2, 19, 15, 0, 0), 200.0)):
            create_tx(
                TransactionCreate(
                    timestamp=ts,
                    type=TransactionType.INVESTMENT_BUY,
                    entity_id=self.eid,
                    currency="USD",
                    total_value=value,
                    portfolio_asset_id=self.pa_id,
                    quantity=1,
                    unit_price=value,
                ),
                conn=self.conn,
            )

        self.assertEqual(self._adjustment_count(), 1)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-02-18T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 300.0, places=2)

    def test_backdated_buy_before_later_snapshot_still_injects(self):
        """Only a *prior* snapshot blocks injection; a later snapshot does not."""
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        queries.create_balance_snapshot(
            self.conn,
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp="2025-06-01T00:00:00",
        )

        create_tx(
            TransactionCreate(
                timestamp=datetime(2025, 2, 19, 10, 0, 0),
                type=TransactionType.INVESTMENT_BUY,
                entity_id=self.eid,
                currency="USD",
                total_value=90000.0,
                portfolio_asset_id=self.pa_id,
                quantity=50,
                unit_price=1800.0,
            ),
            conn=self.conn,
        )

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-02-18T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 90000.0, places=2)


class TestSpendCashHandling(unittest.TestCase):
    """Inject/debit cash handling for spends (INVESTMENT_BUY, MONEY_OUT,
    TRANSFER_OUT) via the balance_mode override."""

    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)

    def _adjustment_count(self):
        return self.conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE type = 'BALANCE_ADJUSTMENT'").fetchone()[
            "c"
        ]

    def _create_spend(self, type_, ts, value, **kwargs):
        from models import TransactionCreate
        from models.enums import TransactionType
        from services.transaction_svc import create as create_tx

        return create_tx(
            TransactionCreate(
                timestamp=ts,
                type=TransactionType(type_),
                entity_id=self.eid,
                currency="USD",
                total_value=value,
                **kwargs,
            ),
            conn=self.conn,
        )

    def test_money_out_unfunded_injects_by_default(self):
        self._create_spend("MONEY_OUT", datetime(2025, 3, 10, 10, 0, 0), 300.0)
        self.assertEqual(self._adjustment_count(), 1)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-03-09T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 300.0, places=2)

    def test_transfer_out_unfunded_injects_by_default(self):
        self._create_spend("TRANSFER_OUT", datetime(2025, 3, 10, 10, 0, 0), 120.0)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-03-09T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 120.0, places=2)

    def test_debit_mode_blocks_injection(self):
        from db.queries import get_balance_at_date

        self._create_spend("MONEY_OUT", datetime(2025, 3, 10, 10, 0, 0), 300.0, balance_mode="debit")
        self.assertEqual(self._adjustment_count(), 0)
        self.assertAlmostEqual(get_balance_at_date(self.conn, self.eid, "USD", "2025-03-10T23:59:59"), -300.0)

    def test_inject_mode_forces_injection_despite_anchor(self):
        queries.create_balance_snapshot(self.conn, self.eid, "USD", 100.0, "2025-01-01T00:00:00")
        self._create_spend("MONEY_OUT", datetime(2025, 3, 10, 10, 0, 0), 300.0, balance_mode="inject")
        self.assertEqual(self._adjustment_count(), 1)
        adj = queries.get_injected_adjustment_at(self.conn, self.eid, "USD", "2025-03-09T23:59:59")
        self.assertIsNotNone(adj)
        assert adj is not None
        self.assertAlmostEqual(adj["total_value"], 200.0, places=2)

    def test_anchor_debits_without_mode(self):
        queries.create_balance_snapshot(self.conn, self.eid, "USD", 100.0, "2025-01-01T00:00:00")
        self._create_spend("MONEY_OUT", datetime(2025, 3, 10, 10, 0, 0), 300.0)
        self.assertEqual(self._adjustment_count(), 0)

    def test_invalid_balance_mode_rejected(self):
        import pydantic

        from models import TransactionCreate
        from models.enums import TransactionType

        with self.assertRaises(pydantic.ValidationError):
            TransactionCreate(
                timestamp=datetime(2025, 3, 10, 10, 0, 0),
                type=TransactionType.MONEY_OUT,
                entity_id=self.eid,
                currency="USD",
                total_value=300.0,
                balance_mode="nonsense",  # type: ignore[arg-type]
            )


class TestBackfillAutoSnapshots(unittest.TestCase):
    """Regression: startup migration should create anchor snapshots for existing
    INVESTMENT_BUY transactions that were recorded before the auto-snapshot feature."""

    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        queries.create_market_asset(
            self.conn,
            market_code="IWDA.AMS",
            currency_code="USD",
            asset_type="ETF",
            ticker="IWDA",
        )
        self.pa_id = queries.create_portfolio_asset(
            self.conn,
            market_code="IWDA.AMS",
        )

    def _insert_buy(self, eid, currency, ts, total_value):
        """Insert an INVESTMENT_BUY directly into the DB (bypassing runtime logic)."""
        self.conn.execute(
            """INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, portfolio_asset_id)
               VALUES (?, 'INVESTMENT_BUY', ?, ?, ?, ?)""",
            (ts, eid, currency, total_value, self.pa_id),
        )
        self.conn.commit()

    def _insert_money_in(self, eid, currency, ts, total_value):
        self.conn.execute(
            """INSERT INTO transactions (timestamp, type, entity_id, currency, total_value)
               VALUES (?, 'INCOME', ?, ?, ?)""",
            (ts, eid, currency, total_value),
        )
        self.conn.commit()

    def test_backfill_creates_snapshot_for_existing_buy(self):
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)
        snap = snapshots[0]
        self.assertAlmostEqual(snap["amount"], 90000.0, places=2)
        self.assertEqual(snap["timestamp"][:10], "2025-02-18")
        self.assertIn("Auto-migrated", snap["notes"])

    def test_backfill_handles_multiple_buys(self):
        """Backfill processes all buys chronologically, each getting needed cash."""
        self._insert_buy(self.eid, "USD", "2025-06-01T10:00:00", 5000.0)
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 2)
        amounts = sorted([s["amount"] for s in snapshots])
        self.assertAlmostEqual(amounts[0], 5000.0, places=2)
        self.assertAlmostEqual(amounts[1], 90000.0, places=2)

    def test_backfill_creates_snapshot_for_cash_gap(self):
        """Money in covers only part of the buy → backfill creates snapshot for the gap."""
        self._insert_money_in(self.eid, "USD", "2025-02-10T10:00:00", 50000.0)
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)
        self.assertAlmostEqual(snapshots[0]["amount"], 40000.0, places=2)

    def test_backfill_creates_snapshot_if_prior_insufficient(self):
        """Prior snapshot doesn't cover the buy → backfill adds more."""
        queries.create_balance_snapshot(
            self.conn,
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp="2025-02-18T00:00:00",
        )
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 2)
        amounts = sorted([s["amount"] for s in snapshots])
        self.assertAlmostEqual(amounts[0], 5000.0, places=2)
        self.assertAlmostEqual(amounts[1], 85000.0, places=2)

    def test_backfill_cash_anchors_correctly(self):
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        from db.queries import get_balance_at_date

        cash_after = get_balance_at_date(self.conn, self.eid, "USD", "2025-02-19T23:59:59")
        self.assertAlmostEqual(cash_after, 0.0, places=2)

    def test_backfill_multiple_entity_currency_pairs(self):
        eid2 = seed_entity(self.conn)
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)
        self._insert_buy(eid2, "USD", "2025-03-01T10:00:00", 50000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snaps1 = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        snaps2 = queries.get_snapshots_for_entity(self.conn, eid2, "USD")
        self.assertEqual(len(snaps1), 1)
        self.assertEqual(len(snaps2), 1)
        self.assertAlmostEqual(snaps1[0]["amount"], 90000.0, places=2)
        self.assertAlmostEqual(snaps2[0]["amount"], 50000.0, places=2)

    def test_backfill_is_idempotent(self):
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)
        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)

    def test_backfill_creates_snapshot_when_later_snapshots_exist(self):
        """Buy in 2025, manual snapshots in 2026 — backfill should still create
        the anchor at 2025-02-18 because no snapshot exists at or before the buy."""
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)
        queries.create_balance_snapshot(
            self.conn,
            entity_id=self.eid,
            currency="USD",
            amount=5000.0,
            timestamp="2026-01-15T00:00:00",
        )

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 2)
        timestamps = sorted(s["timestamp"] for s in snapshots)
        self.assertEqual(timestamps[0][:10], "2025-02-18")
        self.assertEqual(timestamps[1][:10], "2026-01-15")

    def test_backfill_money_in_same_day_as_buy(self):
        """INCOME on the same day as the buy — cash at (buy - 1 day) is still 0,
        so a snapshot is created for the full buy amount."""
        self._insert_money_in(self.eid, "USD", "2025-02-19T08:00:00", 50000.0)
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)
        self.assertAlmostEqual(snapshots[0]["amount"], 90000.0, places=2)

    def test_backfill_money_in_after_buy_does_not_block(self):
        """INCOME after the buy should not prevent auto-snapshot for the earlier buy."""
        self._insert_buy(self.eid, "USD", "2025-02-19T10:00:00", 90000.0)
        self._insert_money_in(self.eid, "USD", "2025-06-01T10:00:00", 10000.0)

        from db.connection import _backfill_auto_snapshots

        _backfill_auto_snapshots(self.conn)

        snapshots = queries.get_snapshots_for_entity(self.conn, self.eid, "USD")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["timestamp"][:10], "2025-02-18")


class TestConsolidateAutoSnapshots(unittest.TestCase):
    """Migration 016: auto-snapshots -> injected BALANCE_ADJUSTMENT + re-derive
    manual snapshot adjustments."""

    def setUp(self):
        self.conn = in_memory_db()
        self.eid = seed_entity(self.conn)
        seed_currency(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run(self):
        import importlib

        mod = importlib.import_module("db.migrations.016_consolidate_auto_snapshots")
        mod.up(self.conn)

    def test_consolidates_auto_snapshots_and_rederives_adjustments(self):
        # Manual snapshot anchor (survives)
        mid = queries.create_balance_snapshot(self.conn, self.eid, "USD", 500.0, "2026-03-01T00:00:00", notes=None)
        # Stale auto-snapshots (to be deleted), including a duplicate timestamp
        queries.create_balance_snapshot(
            self.conn, self.eid, "USD", 999999.0, "2025-01-01T00:00:00", "Auto-created: inferred cash"
        )
        queries.create_balance_snapshot(
            self.conn, self.eid, "USD", 111111.0, "2025-01-01T00:00:00", "Auto-migrated: inferred cash"
        )
        queries.create_balance_snapshot(
            self.conn, self.eid, "USD", 12345.0, "2025-02-01T00:00:00", "Auto-created: inferred cash"
        )
        # Stale linked adjustment (to be replaced)
        queries.create_adjustment_transaction(self.conn, self.eid, "USD", 999.0, "2026-02-28T00:00:00", mid, "stale")

        # Transactions
        queries.create_transaction(self.conn, "2025-01-02T00:00:00", "INVESTMENT_BUY", self.eid, "USD", 100.0)
        queries.create_transaction(self.conn, "2025-02-02T00:00:00", "INVESTMENT_BUY", self.eid, "USD", 200.0)
        queries.create_transaction(self.conn, "2025-02-15T00:00:00", "INVESTMENT_SELL", self.eid, "USD", 350.0)

        self._run()

        # Auto snapshots deleted; manual snapshot remains
        auto = self.conn.execute("SELECT COUNT(*) AS c FROM balance_snapshots WHERE notes LIKE 'Auto-%'").fetchone()
        self.assertEqual(auto["c"], 0)
        manual = self.conn.execute("SELECT COUNT(*) AS c FROM balance_snapshots WHERE id = ?", (mid,)).fetchone()
        self.assertEqual(manual["c"], 1)

        # Injected cash (balance_snapshot_id NULL): minimal, anchored on the manual snapshot
        inj = self.conn.execute(
            "SELECT timestamp, total_value FROM transactions WHERE type='BALANCE_ADJUSTMENT' AND balance_snapshot_id IS NULL ORDER BY timestamp"
        ).fetchall()
        self.assertEqual(len(inj), 2)
        self.assertEqual(inj[0]["timestamp"], "2025-01-01T23:59:59")
        self.assertAlmostEqual(inj[0]["total_value"], 100.0)
        self.assertEqual(inj[1]["timestamp"], "2025-02-01T23:59:59")
        self.assertAlmostEqual(inj[1]["total_value"], 200.0)

        # Manual snapshot's own adjustment: target - computed = 500 - 350 = 150
        adj = self.conn.execute(
            "SELECT timestamp, total_value FROM transactions WHERE type='BALANCE_ADJUSTMENT' AND balance_snapshot_id = ?",
            (mid,),
        ).fetchone()
        self.assertIsNotNone(adj)
        self.assertEqual(adj["timestamp"], "2026-02-28T23:59:59")
        self.assertAlmostEqual(adj["total_value"], 150.0)

        # Continuity: actual balance at the manual snapshot date lands on its target
        balance = queries.get_balance_at_date(self.conn, self.eid, "USD", "2026-03-01T00:00:00")
        self.assertAlmostEqual(balance, 500.0, places=2)


if __name__ == "__main__":
    unittest.main()
