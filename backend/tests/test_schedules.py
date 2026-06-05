import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models import TransactionCreate
from models.enums import EntityType, PeriodicityType
from routes.schedules import router
from services.transaction_svc import FKNotFound

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


def seed_transaction(conn: sqlite3.Connection) -> int:
    return queries.create_transaction(
        conn, timestamp="2024-06-01T10:00:00", type_="INVESTMENT_BUY",
        entity_id=seed_entity(conn), currency="USD", total_value=100.0,
    )


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestScheduleQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_schedules(self.conn), [])

    def test_create_returns_id(self):
        sid = queries.create_schedule(
            self.conn, "My Schedule", "2025-01-01", "MONTHLY",
        )
        self.assertIsInstance(sid, int)
        self.assertGreater(sid, 0)

    def test_get_returns_row(self):
        sid = queries.create_schedule(
            self.conn, "My Schedule", "2025-01-01", "MONTHLY",
        )
        row = queries.get_schedule(self.conn, sid)
        self.assertIsNotNone(row)
        self.assertEqual(row["description"], "My Schedule")
        self.assertEqual(row["periodicity_type"], "MONTHLY")

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_schedule(self.conn, 999))

    def test_create_with_all_fields(self):
        sid = queries.create_schedule(
            self.conn, "Full Schedule", "2025-01-01", "CUSTOM",
            end_date="2025-12-31", custom_cron="0 0 1 * *",
        )
        row = queries.get_schedule(self.conn, sid)
        self.assertEqual(row["end_date"], "2025-12-31")
        self.assertEqual(row["custom_cron"], "0 0 1 * *")

    def test_get_all_returns_all(self):
        queries.create_schedule(self.conn, "S1", "2025-01-01", "MONTHLY")
        queries.create_schedule(self.conn, "S2", "2025-01-01", "WEEKLY")
        self.assertEqual(len(queries.get_all_schedules(self.conn)), 2)

    def test_update_returns_true(self):
        sid = queries.create_schedule(
            self.conn, "Original", "2025-01-01", "MONTHLY",
        )
        ok = queries.update_schedule(
            self.conn, sid, "Updated", "2025-01-01", "WEEKLY",
        )
        self.assertTrue(ok)
        row = queries.get_schedule(self.conn, sid)
        self.assertEqual(row["description"], "Updated")
        self.assertEqual(row["periodicity_type"], "WEEKLY")

    def test_update_nonexistent(self):
        ok = queries.update_schedule(self.conn, 999, "Nope", "2025-01-01", "MONTHLY")
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        sid = queries.create_schedule(
            self.conn, "To Delete", "2025-01-01", "MONTHLY",
        )
        ok = queries.delete_schedule(self.conn, sid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_schedule(self.conn, sid))

    def test_delete_nonexistent(self):
        ok = queries.delete_schedule(self.conn, 999)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestScheduleService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patchers = [
            patch("services.schedule_svc.get_db", return_value=self.conn),
            patch("services.schedule_svc.sync_schedule"),
            patch("services.schedule_svc.remove_schedule"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()


    def import_service(self):
        from services import schedule_svc
        return schedule_svc

    def test_create_minimal(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(
            description="Monthly DCA",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
        )
        result = svc.create(body)
        self.assertIsNotNone(result.id)
        self.assertEqual(result.description, "Monthly DCA")
        self.assertEqual(result.periodicity_type, PeriodicityType.MONTHLY)
        self.assertIsNone(result.end_date)
        self.assertIsNone(result.custom_cron)
        self.assertIsNone(result.linked_transaction_id)

    def test_create_with_all_fields(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(
            description="Custom Schedule",
            start_date="2025-01-01",
            end_date="2025-12-31",
            periodicity_type="CUSTOM",
            custom_cron="0 0 1 * *",
        )
        result = svc.create(body)
        self.assertEqual(result.end_date, body.end_date)
        self.assertEqual(result.custom_cron, "0 0 1 * *")

    def test_create_with_linked_transaction(self):
        seed_currency(self.conn)
        tx_id = seed_transaction(self.conn)
        svc = self.import_service()
        body = svc.ScheduleCreate(
            description="Linked",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
            linked_transaction_id=tx_id,
        )
        result = svc.create(body)
        self.assertEqual(result.linked_transaction_id, tx_id)

    def test_create_transaction_not_found(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(
            description="Broken",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
            linked_transaction_id=999,
        )
        with self.assertRaises(svc.TransactionNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(
            description="Get Me",
            start_date="2025-01-01",
            periodicity_type="WEEKLY",
        )
        created = svc.create(body)
        result = svc.get(created.id)
        self.assertEqual(result.description, "Get Me")

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.ScheduleNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.ScheduleCreate(description="S1", start_date="2025-01-01", periodicity_type="MONTHLY"))
        svc.create(svc.ScheduleCreate(description="S2", start_date="2025-01-01", periodicity_type="WEEKLY"))
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(description="Original", start_date="2025-01-01", periodicity_type="MONTHLY")
        created = svc.create(body)
        updated_body = svc.ScheduleCreate(description="Updated", start_date="2025-01-01", periodicity_type="WEEKLY")
        result = svc.update(created.id, updated_body)
        self.assertEqual(result.description, "Updated")
        self.assertEqual(result.periodicity_type, PeriodicityType.WEEKLY)

    def test_update_not_found(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(description="Nope", start_date="2025-01-01", periodicity_type="MONTHLY")
        with self.assertRaises(svc.ScheduleNotFound):
            svc.update(999, body)

    def test_update_with_valid_transaction(self):
        seed_currency(self.conn)
        tx_id = seed_transaction(self.conn)
        svc = self.import_service()
        body = svc.ScheduleCreate(description="Original", start_date="2025-01-01", periodicity_type="MONTHLY")
        created = svc.create(body)
        updated_body = svc.ScheduleCreate(
            description="With Link", start_date="2025-01-01",
            periodicity_type="MONTHLY", linked_transaction_id=tx_id,
        )
        result = svc.update(created.id, updated_body)
        self.assertEqual(result.linked_transaction_id, tx_id)

    def test_delete(self):
        svc = self.import_service()
        body = svc.ScheduleCreate(description="Delete Me", start_date="2025-01-01", periodicity_type="MONTHLY")
        created = svc.create(body)
        svc.delete(created.id)
        with self.assertRaises(svc.ScheduleNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.ScheduleNotFound):
            svc.delete(999)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestScheduleRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.patchers = [
            patch("services.schedule_svc.get_db", return_value=self.conn),
            patch("services.schedule_svc.sync_schedule"),
            patch("services.schedule_svc.remove_schedule"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()


    def test_list_empty(self):
        resp = client.get("/api/v1/schedules")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create_minimal(self):
        resp = client.post("/api/v1/schedules", json={
            "description": "Monthly DCA",
            "start_date": "2025-01-01",
            "periodicity_type": "MONTHLY",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["description"], "Monthly DCA")
        self.assertEqual(data["periodicity_type"], "MONTHLY")
        self.assertIn("id", data)
        self.assertIsNone(data.get("end_date"))
        self.assertIsNone(data.get("custom_cron"))
        self.assertIsNone(data.get("linked_transaction_id"))

    def test_create_with_all_fields(self):
        resp = client.post("/api/v1/schedules", json={
            "description": "Full",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "periodicity_type": "CUSTOM",
            "custom_cron": "0 0 1 * *",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["end_date"], "2025-12-31")
        self.assertEqual(data["custom_cron"], "0 0 1 * *")

    def test_create_with_linked_transaction(self):
        tx_id = seed_transaction(self.conn)
        resp = client.post("/api/v1/schedules", json={
            "description": "Linked",
            "start_date": "2025-01-01",
            "periodicity_type": "MONTHLY",
            "linked_transaction_id": tx_id,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["linked_transaction_id"], tx_id)

    def test_create_transaction_not_found(self):
        resp = client.post("/api/v1/schedules", json={
            "description": "Broken",
            "start_date": "2025-01-01",
            "periodicity_type": "MONTHLY",
            "linked_transaction_id": 999,
        })
        self.assertEqual(resp.status_code, 422)

    def test_get(self):
        create_resp = client.post("/api/v1/schedules", json={
            "description": "Get Me",
            "start_date": "2025-01-01",
            "periodicity_type": "WEEKLY",
        })
        sid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/schedules/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["description"], "Get Me")

    def test_get_not_found(self):
        resp = client.get("/api/v1/schedules/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post("/api/v1/schedules", json={
            "description": "S1", "start_date": "2025-01-01", "periodicity_type": "MONTHLY",
        })
        client.post("/api/v1/schedules", json={
            "description": "S2", "start_date": "2025-01-01", "periodicity_type": "WEEKLY",
        })
        resp = client.get("/api/v1/schedules")
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        create_resp = client.post("/api/v1/schedules", json={
            "description": "Original", "start_date": "2025-01-01", "periodicity_type": "MONTHLY",
        })
        sid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/schedules/{sid}", json={
            "description": "Updated", "start_date": "2025-01-01", "periodicity_type": "WEEKLY",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["description"], "Updated")

    def test_update_not_found(self):
        resp = client.put("/api/v1/schedules/999", json={
            "description": "Nope", "start_date": "2025-01-01", "periodicity_type": "MONTHLY",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/schedules", json={
            "description": "Delete Me", "start_date": "2025-01-01", "periodicity_type": "MONTHLY",
        })
        sid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/schedules/{sid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/schedules/{sid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/schedules/999")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Full schedule (composite) tests
# ---------------------------------------------------------------------------

class TestScheduleFullService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        self.patchers = [
            patch("services.schedule_full_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.schedule_svc.get_db", return_value=self.conn),
            patch("services.schedule_full_svc.sync_schedule"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()


    def import_svc(self):
        from services import schedule_full_svc
        return schedule_full_svc

    def default_body(self):
        from models import ScheduleCreate, ScheduleFullCreate
        return ScheduleFullCreate(
            schedule=ScheduleCreate(
                description="Monthly DCA",
                start_date="2025-01-01",
                periodicity_type="MONTHLY",
            ),
            transaction=TransactionCreate(
                timestamp=datetime(2024, 6, 1, 10, 0, 0),
                type="INVESTMENT_BUY",
                entity_id=self.eid,
                currency="USD",
                quantity=10.0,
                unit_price=50.0,
            ),
        )

    def test_create_basic(self):
        svc = self.import_svc()
        result = svc.create(self.default_body())
        self.assertIsNotNone(result.schedule.id)
        self.assertIsNotNone(result.transaction.id)
        self.assertEqual(result.schedule.description, "Monthly DCA")
        self.assertEqual(result.transaction.total_value, 500.0)
        self.assertEqual(result.schedule.linked_transaction_id, result.transaction.id)

    def test_create_rollback_on_bad_fk(self):
        svc = self.import_svc()
        body = self.default_body()
        body.transaction.entity_id = 999
        with self.assertRaises(FKNotFound):
            svc.create(body)
        remaining = queries.get_all_schedules(self.conn)
        self.assertEqual(len(remaining), 0, "No schedule should remain after rollback")


class TestScheduleFullRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        self.patchers = [
            patch("services.schedule_full_svc.get_db", return_value=self.conn),
            patch("services.transaction_svc.get_db", return_value=self.conn),
            patch("services.schedule_svc.get_db", return_value=self.conn),
            patch("services.schedule_svc.sync_schedule"),
            patch("services.schedule_full_svc.sync_schedule"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.conn.close()

    def default_payload(self):
        return {
            "schedule": {
                "description": "Monthly DCA",
                "start_date": "2025-01-01",
                "periodicity_type": "MONTHLY",
            },
            "transaction": {
                "timestamp": "2024-06-01T10:00:00",
                "type": "INVESTMENT_BUY",
                "entity_id": self.eid,
                "currency": "USD",
                "quantity": 10.0,
                "unit_price": 50.0,
            },
        }

    def test_create_basic(self):
        resp = client.post("/api/v1/schedules/full", json=self.default_payload())
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("schedule", data)
        self.assertIn("transaction", data)
        self.assertEqual(data["schedule"]["description"], "Monthly DCA")
        self.assertEqual(data["transaction"]["total_value"], 500.0)
        self.assertEqual(
            data["schedule"]["linked_transaction_id"],
            data["transaction"]["id"],
        )

    def test_create_bad_fk(self):
        payload = self.default_payload()
        payload["transaction"]["entity_id"] = 999
        resp = client.post("/api/v1/schedules/full", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_create_missing_schedule_field(self):
        resp = client.post("/api/v1/schedules/full", json={
            "transaction": {
                "timestamp": "2024-06-01T10:00:00",
                "type": "INVESTMENT_BUY",
                "entity_id": self.eid,
                "currency": "USD",
                "quantity": 10.0,
                "unit_price": 50.0,
            },
        })
        self.assertEqual(resp.status_code, 422)

    def test_create_missing_transaction_field(self):
        resp = client.post("/api/v1/schedules/full", json={
            "schedule": {
                "description": "Monthly DCA",
                "start_date": "2025-01-01",
                "periodicity_type": "MONTHLY",
            },
        })
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
