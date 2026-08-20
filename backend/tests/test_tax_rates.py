"""Tests for tax rate CRUD queries and service (§17.8)."""

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.tax_rates import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    # Insert a default profile so _profile_clause works.
    conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
    conn.commit()
    return conn


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestTaxRateQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_returns_id(self):
        rid = queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19, to_amount=6000, year_start=2024)
        self.assertGreater(rid, 0)

    def test_create_and_get(self):
        rid = queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.21, to_amount=50000, year_start=2024)
        row = queries.get_tax_rate(self.conn, rid)
        assert row is not None
        self.assertEqual(row["ruleset_key"], "spain")
        self.assertEqual(row["category"], "capital_gains")
        self.assertAlmostEqual(row["rate"], 0.21)

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_tax_rate(self.conn, 999))

    def test_get_all(self):
        queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19, to_amount=6000)
        queries.create_tax_rate(self.conn, "japan", "capital_gains", 0, 0.20315)
        rows = queries.get_all_tax_rates(self.conn)
        self.assertEqual(len(rows), 2)

    def test_get_for_ruleset(self):
        queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19, to_amount=6000)
        queries.create_tax_rate(self.conn, "japan", "capital_gains", 0, 0.20315)
        rows = queries.get_tax_rates_for_ruleset(self.conn, "spain")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ruleset_key"], "spain")

    def test_get_for_ruleset_category_filter(self):
        queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19)
        queries.create_tax_rate(self.conn, "spain", "dividends", 0, 0.19)
        rows = queries.get_tax_rates_for_ruleset(self.conn, "spain", category="capital_gains")
        self.assertEqual(len(rows), 1)

    def test_update(self):
        rid = queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19)
        ok = queries.update_tax_rate(self.conn, rid, "spain", "capital_gains", 0, 0.21, to_amount=50000)
        self.assertTrue(ok)
        row = queries.get_tax_rate(self.conn, rid)
        assert row is not None
        self.assertAlmostEqual(row["rate"], 0.21)

    def test_delete(self):
        rid = queries.create_tax_rate(self.conn, "spain", "capital_gains", 0, 0.19)
        ok = queries.delete_tax_rate(self.conn, rid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_tax_rate(self.conn, rid))


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestTaxRateService(unittest.TestCase):
    def setUp(self):
        self._conn = in_memory_db()

    def tearDown(self):
        self._conn.close()

    @patch("services.tax_rate_svc.get_db")
    def test_create_service(self, mock_get_db):
        mock_get_db.return_value = self._conn
        from models import TaxRateCreate
        from services import tax_rate_svc

        body = TaxRateCreate(ruleset_key="spain", category="capital_gains", from_amount=0, rate=0.19, to_amount=6000)
        resp = tax_rate_svc.create(body)
        self.assertEqual(resp.ruleset_key, "spain")
        self.assertAlmostEqual(resp.rate, 0.19)

    @patch("services.tax_rate_svc.get_db")
    def test_get_service(self, mock_get_db):
        mock_get_db.return_value = self._conn
        from models import TaxRateCreate
        from services import tax_rate_svc

        body = TaxRateCreate(ruleset_key="japan", category="capital_gains", from_amount=0, rate=0.20315)
        created = tax_rate_svc.create(body)
        got = tax_rate_svc.get(created.id)
        self.assertEqual(got.ruleset_key, "japan")

    @patch("services.tax_rate_svc.get_db")
    def test_list_service(self, mock_get_db):
        mock_get_db.return_value = self._conn
        from models import TaxRateCreate
        from services import tax_rate_svc

        tax_rate_svc.create(TaxRateCreate(ruleset_key="spain", category="capital_gains", from_amount=0, rate=0.19))
        tax_rate_svc.create(TaxRateCreate(ruleset_key="japan", category="capital_gains", from_amount=0, rate=0.20315))
        self.assertEqual(len(tax_rate_svc.list_all()), 2)
        self.assertEqual(len(tax_rate_svc.list_all(ruleset_key="spain")), 1)

    @patch("services.tax_rate_svc.get_db")
    def test_delete_service(self, mock_get_db):
        mock_get_db.return_value = self._conn
        from models import TaxRateCreate
        from services import tax_rate_svc

        created = tax_rate_svc.create(
            TaxRateCreate(ruleset_key="spain", category="capital_gains", from_amount=0, rate=0.19)
        )
        tax_rate_svc.delete(created.id)
        with self.assertRaises(tax_rate_svc.TaxRateNotFound):
            tax_rate_svc.get(created.id)


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------


class TestTaxRateAPI(unittest.TestCase):
    def setUp(self):
        self._conn = in_memory_db()
        self._patcher = patch("services.tax_rate_svc.get_db", return_value=self._conn)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/tax-rates")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create_and_get(self):
        body = {"ruleset_key": "spain", "category": "capital_gains", "from_amount": 0, "rate": 0.19, "to_amount": 6000}
        resp = client.post("/api/v1/tax-rates", json=body)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["ruleset_key"], "spain")
        rid = data["id"]

        resp = client.get(f"/api/v1/tax-rates/{rid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], rid)

    def test_update(self):
        body = {"ruleset_key": "spain", "category": "capital_gains", "from_amount": 0, "rate": 0.19}
        resp = client.post("/api/v1/tax-rates", json=body)
        rid = resp.json()["id"]
        body["rate"] = 0.21
        resp = client.put(f"/api/v1/tax-rates/{rid}", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["rate"], 0.21)

    def test_delete(self):
        body = {"ruleset_key": "spain", "category": "capital_gains", "from_amount": 0, "rate": 0.19}
        resp = client.post("/api/v1/tax-rates", json=body)
        rid = resp.json()["id"]
        resp = client.delete(f"/api/v1/tax-rates/{rid}")
        self.assertEqual(resp.status_code, 204)

    def test_get_nonexistent(self):
        resp = client.get("/api/v1/tax-rates/999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_nonexistent(self):
        resp = client.delete("/api/v1/tax-rates/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
