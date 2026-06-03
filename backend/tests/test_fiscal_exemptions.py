import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.fiscal_exemptions import router

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

class TestFiscalExemptionQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_fiscal_exemptions(self.conn), [])

    def test_create_returns_id(self):
        eid = queries.create_fiscal_exemption(self.conn, "NISA")
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_create_with_defaults(self):
        eid = queries.create_fiscal_exemption(self.conn, "ISA")
        row = queries.get_fiscal_exemption(self.conn, eid)
        self.assertEqual(row["exemption_type"], "ISA")
        self.assertEqual(row["exemption_amount"], 0)
        self.assertEqual(row["exemption_rate"], 100)
        self.assertIsNone(row["exemption_rate_limit"])
        self.assertIsNone(row["description"])

    def test_create_with_all_fields(self):
        eid = queries.create_fiscal_exemption(
            self.conn, "401k", "Retirement", 19500, 100, 100000
        )
        row = queries.get_fiscal_exemption(self.conn, eid)
        self.assertEqual(row["exemption_type"], "401k")
        self.assertEqual(row["description"], "Retirement")
        self.assertEqual(row["exemption_amount"], 19500)
        self.assertEqual(row["exemption_rate"], 100)
        self.assertEqual(row["exemption_rate_limit"], 100000)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_fiscal_exemption(self.conn, 999))

    def test_get_all_returns_all(self):
        queries.create_fiscal_exemption(self.conn, "NISA")
        queries.create_fiscal_exemption(self.conn, "ISA")
        all_items = queries.get_all_fiscal_exemptions(self.conn)
        self.assertEqual(len(all_items), 2)

    def test_update_returns_true(self):
        eid = queries.create_fiscal_exemption(self.conn, "Old")
        ok = queries.update_fiscal_exemption(self.conn, eid, "New", exemption_rate=50)
        self.assertTrue(ok)
        row = queries.get_fiscal_exemption(self.conn, eid)
        self.assertEqual(row["exemption_type"], "New")
        self.assertEqual(row["exemption_rate"], 50)

    def test_update_nonexistent(self):
        ok = queries.update_fiscal_exemption(self.conn, 999, "Nope")
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        eid = queries.create_fiscal_exemption(self.conn, "Del")
        ok = queries.delete_fiscal_exemption(self.conn, eid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_fiscal_exemption(self.conn, eid))

    def test_delete_nonexistent(self):
        ok = queries.delete_fiscal_exemption(self.conn, 999)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestFiscalExemptionService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.fiscal_exemption_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import fiscal_exemption_svc
        return fiscal_exemption_svc

    def test_create_minimal(self):
        svc = self.import_service()
        body = svc.FiscalExemptionCreate(exemption_type="NISA")
        result = svc.create(body)
        self.assertEqual(result.exemption_type, "NISA")
        self.assertEqual(result.exemption_amount, 0)
        self.assertEqual(result.exemption_rate, 100)
        self.assertIsNone(result.exemption_rate_limit)
        self.assertIsNotNone(result.id)

    def test_create_with_all_fields(self):
        svc = self.import_service()
        body = svc.FiscalExemptionCreate(
            exemption_type="401k",
            description="Retirement",
            exemption_amount=19500,
            exemption_rate=100,
            exemption_rate_limit=100000,
        )
        result = svc.create(body)
        self.assertEqual(result.exemption_amount, 19500)
        self.assertEqual(result.exemption_rate_limit, 100000)

    def test_get(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalExemptionCreate(exemption_type="ISA"))
        result = svc.get(created.id)
        self.assertEqual(result.exemption_type, "ISA")

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.FiscalExemptionNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.FiscalExemptionCreate(exemption_type="A"))
        svc.create(svc.FiscalExemptionCreate(exemption_type="B"))
        result = svc.list_all()
        self.assertEqual(len(result), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalExemptionCreate(exemption_type="Old"))
        result = svc.update(created.id, svc.FiscalExemptionCreate(
            exemption_type="New", exemption_rate=50
        ))
        self.assertEqual(result.exemption_type, "New")
        self.assertEqual(result.exemption_rate, 50)
        self.assertEqual(result.id, created.id)

    def test_update_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.FiscalExemptionNotFound):
            svc.update(999, svc.FiscalExemptionCreate(exemption_type="X"))

    def test_delete(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalExemptionCreate(exemption_type="Del"))
        svc.delete(created.id)
        with self.assertRaises(svc.FiscalExemptionNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.FiscalExemptionNotFound):
            svc.delete(999)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestFiscalExemptionRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.fiscal_exemption_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/fiscal-exemptions")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create_minimal(self):
        resp = client.post("/api/v1/fiscal-exemptions", json={
            "exemption_type": "NISA",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["exemption_type"], "NISA")
        self.assertEqual(data["exemption_amount"], 0)
        self.assertEqual(data["exemption_rate"], 100)
        self.assertIn("id", data)

    def test_create_with_all_fields(self):
        resp = client.post("/api/v1/fiscal-exemptions", json={
            "exemption_type": "401k",
            "description": "Retirement",
            "exemption_amount": 19500,
            "exemption_rate": 100,
            "exemption_rate_limit": 100000,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["exemption_amount"], 19500)
        self.assertEqual(data["exemption_rate_limit"], 100000)

    def test_get_exemption(self):
        create_resp = client.post("/api/v1/fiscal-exemptions", json={
            "exemption_type": "ISA",
        })
        eid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/fiscal-exemptions/{eid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["exemption_type"], "ISA")

    def test_get_not_found(self):
        resp = client.get("/api/v1/fiscal-exemptions/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post("/api/v1/fiscal-exemptions", json={"exemption_type": "A"})
        client.post("/api/v1/fiscal-exemptions", json={"exemption_type": "B"})
        resp = client.get("/api/v1/fiscal-exemptions")
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        create_resp = client.post("/api/v1/fiscal-exemptions", json={
            "exemption_type": "Old",
        })
        eid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/fiscal-exemptions/{eid}", json={
            "exemption_type": "New",
            "exemption_rate": 50,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["exemption_type"], "New")
        self.assertEqual(resp.json()["exemption_rate"], 50)

    def test_update_not_found(self):
        resp = client.put("/api/v1/fiscal-exemptions/999", json={
            "exemption_type": "Nope",
        })
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/fiscal-exemptions", json={
            "exemption_type": "Del",
        })
        eid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/fiscal-exemptions/{eid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/fiscal-exemptions/{eid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/fiscal-exemptions/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
