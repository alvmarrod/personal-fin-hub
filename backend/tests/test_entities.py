import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import EntityType
from routes.entities import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestEntityQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_get_all_entities_empty(self):
        self.assertEqual(queries.get_all_entities(self.conn), [])

    def test_create_entity_returns_id(self):
        eid = queries.create_entity(self.conn, "Test Broker", EntityType.BROKER)
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_create_entity_with_all_fields(self):
        eid = queries.create_entity(
            self.conn, "Test Broker", EntityType.BROKER, "US", "A test broker"
        )
        row = queries.get_entity(self.conn, eid)
        self.assertEqual(row["name"], "Test Broker")
        self.assertEqual(row["entity_type"], "BROKER")
        self.assertEqual(row["country"], "US")
        self.assertEqual(row["description"], "A test broker")

    def test_get_entity_nonexistent(self):
        self.assertIsNone(queries.get_entity(self.conn, 999))

    def test_get_all_entities_returns_all(self):
        queries.create_entity(self.conn, "Broker A", EntityType.BROKER)
        queries.create_entity(self.conn, "Bank B", EntityType.BANK)
        all_entities = queries.get_all_entities(self.conn)
        self.assertEqual(len(all_entities), 2)

    def test_update_entity_returns_true(self):
        eid = queries.create_entity(self.conn, "Old Name", EntityType.BROKER)
        ok = queries.update_entity(self.conn, eid, "New Name", EntityType.BROKER, "ES")
        self.assertTrue(ok)
        row = queries.get_entity(self.conn, eid)
        self.assertEqual(row["name"], "New Name")
        self.assertEqual(row["country"], "ES")

    def test_update_entity_nonexistent(self):
        ok = queries.update_entity(self.conn, 999, "Name", EntityType.OTHER)
        self.assertFalse(ok)

    def test_delete_entity_returns_true(self):
        eid = queries.create_entity(self.conn, "To Delete", EntityType.OTHER)
        ok = queries.delete_entity(self.conn, eid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_entity(self.conn, eid))

    def test_delete_entity_nonexistent(self):
        ok = queries.delete_entity(self.conn, 999)
        self.assertFalse(ok)

    def test_entity_exists(self):
        queries.create_entity(self.conn, "My Broker", EntityType.BROKER)
        self.assertTrue(queries.entity_exists(self.conn, "My Broker", EntityType.BROKER))
        self.assertFalse(queries.entity_exists(self.conn, "My Broker", EntityType.BANK))
        self.assertFalse(queries.entity_exists(self.conn, "Other", EntityType.BROKER))


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestEntityService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.entity_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import entity_svc
        return entity_svc

    def test_create(self):
        svc = self.import_service()
        body = svc.EntityCreate(name="Test Broker", entity_type=EntityType.BROKER)
        result = svc.create(body)
        self.assertEqual(result.name, "Test Broker")
        self.assertEqual(result.entity_type, EntityType.BROKER)
        self.assertIsNone(result.country)
        self.assertIsNone(result.description)
        self.assertIsNotNone(result.id)

    def test_create_duplicate(self):
        svc = self.import_service()
        body = svc.EntityCreate(name="Test", entity_type=EntityType.BROKER)
        svc.create(body)
        with self.assertRaises(svc.EntityAlreadyExists):
            svc.create(body)

    def test_get(self):
        svc = self.import_service()
        created = svc.create(svc.EntityCreate(name="Test", entity_type=EntityType.BANK))
        result = svc.get(created.id)
        self.assertEqual(result.name, "Test")
        self.assertEqual(result.entity_type, EntityType.BANK)

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.EntityNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.EntityCreate(name="A", entity_type=EntityType.BROKER))
        svc.create(svc.EntityCreate(name="B", entity_type=EntityType.BANK))
        result = svc.list_all()
        self.assertEqual(len(result), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_service()
        created = svc.create(svc.EntityCreate(name="Old", entity_type=EntityType.BROKER))
        result = svc.update(created.id, svc.EntityCreate(name="New", entity_type=EntityType.BROKER, country="FR"))
        self.assertEqual(result.name, "New")
        self.assertEqual(result.country, "FR")
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.EntityNotFound):
            svc.update(999, svc.EntityCreate(name="X", entity_type=EntityType.OTHER))

    def test_update_duplicate(self):
        svc = self.import_service()
        svc.create(svc.EntityCreate(name="Existing", entity_type=EntityType.BROKER))
        created = svc.create(svc.EntityCreate(name="Other", entity_type=EntityType.BANK))
        with self.assertRaises(svc.EntityAlreadyExists):
            svc.update(created.id, svc.EntityCreate(name="Existing", entity_type=EntityType.BROKER))

    def test_update_same_name_no_conflict(self):
        svc = self.import_service()
        created = svc.create(svc.EntityCreate(name="Same", entity_type=EntityType.BROKER))
        result = svc.update(created.id, svc.EntityCreate(name="Same", entity_type=EntityType.BROKER))
        self.assertEqual(result.name, "Same")

    def test_delete(self):
        svc = self.import_service()
        created = svc.create(svc.EntityCreate(name="Del", entity_type=EntityType.OTHER))
        svc.delete(created.id)
        with self.assertRaises(svc.EntityNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.EntityNotFound):
            svc.delete(999)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestEntityRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.entity_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_entities_empty(self):
        resp = client.get("/api/v1/entities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create_entity(self):
        resp = client.post("/api/v1/entities", json={
            "name": "My Broker",
            "entity_type": "BROKER",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "My Broker")
        self.assertEqual(data["entity_type"], "BROKER")
        self.assertIn("id", data)

    def test_create_entity_duplicate(self):
        client.post("/api/v1/entities", json={
            "name": "My Broker",
            "entity_type": "BROKER",
        })
        resp = client.post("/api/v1/entities", json={
            "name": "My Broker",
            "entity_type": "BROKER",
        })
        self.assertEqual(resp.status_code, 409)

    def test_get_entity(self):
        create_resp = client.post("/api/v1/entities", json={
            "name": "Get Test",
            "entity_type": "BANK",
            "country": "JP",
        })
        eid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/entities/{eid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Get Test")
        self.assertEqual(resp.json()["country"], "JP")

    def test_get_entity_not_found(self):
        resp = client.get("/api/v1/entities/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_entities(self):
        client.post("/api/v1/entities", json={"name": "A", "entity_type": "BROKER"})
        client.post("/api/v1/entities", json={"name": "B", "entity_type": "BANK"})
        resp = client.get("/api/v1/entities")
        self.assertEqual(len(resp.json()), 2)

    def test_update_entity(self):
        create_resp = client.post("/api/v1/entities", json={
            "name": "Old",
            "entity_type": "BROKER",
        })
        eid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/entities/{eid}", json={
            "name": "New",
            "entity_type": "BROKER",
            "country": "ES",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "New")
        self.assertEqual(resp.json()["country"], "ES")

    def test_update_entity_duplicate(self):
        client.post("/api/v1/entities", json={"name": "Existing", "entity_type": "BROKER"})
        c2 = client.post("/api/v1/entities", json={"name": "Other", "entity_type": "BANK"})
        resp = client.put(f"/api/v1/entities/{c2.json()['id']}", json={
            "name": "Existing",
            "entity_type": "BROKER",
        })
        self.assertEqual(resp.status_code, 409)

    def test_update_entity_not_found(self):
        resp = client.put("/api/v1/entities/999", json={
            "name": "Nope",
            "entity_type": "BROKER",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete_entity(self):
        create_resp = client.post("/api/v1/entities", json={
            "name": "Del Me",
            "entity_type": "OTHER",
        })
        eid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/entities/{eid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/entities/{eid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_entity_not_found(self):
        resp = client.delete("/api/v1/entities/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
