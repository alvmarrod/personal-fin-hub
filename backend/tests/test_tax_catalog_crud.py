"""Tests for the tax catalog CRUD (§17.7-§17.8).

Covers /tax-bases (with nested categories/rates), /tax-definitions, and
/broker-fee-definitions: query, service, and route layers.
"""

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from db.connection import ProfileScopedConnection
from routes.broker_fee_definitions import router as broker_fee_router
from routes.tax_bases import router as tax_bases_router
from routes.tax_definitions import router as tax_definitions_router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> ProfileScopedConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False, factory=ProfileScopedConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


test_app = FastAPI()
test_app.include_router(broker_fee_router, prefix="/api/v1")
test_app.include_router(tax_bases_router, prefix="/api/v1")
test_app.include_router(tax_definitions_router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestTaxBaseQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_and_get(self):
        base_id = queries.create_tax_base(self.conn, "spain", "Spain Savings", "progressive", year_start=2025)
        row = queries.get_tax_base(self.conn, base_id)
        assert row is not None
        self.assertEqual(row["ruleset_key"], "spain")
        self.assertEqual(row["computation"], "progressive")
        self.assertEqual(row["year_start"], 2025)
        self.assertIsNone(row["flat_rate"])

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_tax_base(self.conn, 999))

    def test_replace_categories_and_rates(self):
        base_id = queries.create_tax_base(self.conn, "spain", "Spain", "progressive")
        queries.replace_tax_base_categories(self.conn, base_id, ["capital_gains", "dividends"])
        queries.replace_tax_base_rates(self.conn, base_id, [{"from_amount": 0, "to_amount": 6000, "rate": 0.19}])
        self.assertEqual(queries.get_tax_base_categories(self.conn, base_id), ["capital_gains", "dividends"])
        rates = queries.get_tax_base_rates(self.conn, base_id)
        self.assertEqual(len(rates), 1)
        self.assertAlmostEqual(rates[0]["rate"], 0.19)

    def test_update_and_delete(self):
        base_id = queries.create_tax_base(self.conn, "spain", "Spain", "progressive")
        self.assertTrue(queries.update_tax_base(self.conn, base_id, "spain", "Spain v2", "flat", flat_rate=0.2))
        row = queries.get_tax_base(self.conn, base_id)
        assert row is not None
        self.assertEqual(row["computation"], "flat")
        self.assertAlmostEqual(row["flat_rate"], 0.2)
        self.assertTrue(queries.delete_tax_base(self.conn, base_id))
        self.assertIsNone(queries.get_tax_base(self.conn, base_id))


class TestTaxDefinitionQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_and_get(self):
        def_id = queries.create_tax_definition(self.conn, "tasa_tobin", "Tasa Tobin", "spain", 0.002)
        row = queries.get_tax_definition(self.conn, def_id)
        assert row is not None
        self.assertEqual(row["slug"], "tasa_tobin")
        self.assertEqual(row["ruleset_key"], "spain")
        self.assertAlmostEqual(row["rate"], 0.002)

    def test_slug_unique(self):
        queries.create_tax_definition(self.conn, "tasa_tobin", "Tasa Tobin")
        with self.assertRaises(sqlite3.IntegrityError):
            queries.create_tax_definition(self.conn, "tasa_tobin", "Duplicate")

    def test_get_by_slug(self):
        def_id = queries.create_tax_definition(self.conn, "withholding", "Withholding")
        row = queries.get_tax_definition_by_slug(self.conn, "withholding")
        assert row is not None
        self.assertEqual(row["id"], def_id)

    def test_count_referenced(self):
        def_id = queries.create_tax_definition(self.conn, "withholding", "Withholding")
        self.assertEqual(queries.count_transaction_taxes_for_definition(self.conn, def_id), 0)


class TestBrokerFeeDefinitionQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_and_get(self):
        def_id = queries.create_broker_fee_definition(self.conn, "Commission")
        row = queries.get_broker_fee_definition(self.conn, def_id)
        assert row is not None
        self.assertEqual(row["name"], "Commission")
        self.assertEqual(len(queries.get_all_broker_fee_definitions(self.conn)), 1)

    def test_update_and_delete(self):
        def_id = queries.create_broker_fee_definition(self.conn, "Commission")
        self.assertTrue(queries.update_broker_fee_definition(self.conn, def_id, "Rebate"))
        self.assertTrue(queries.delete_broker_fee_definition(self.conn, def_id))
        self.assertIsNone(queries.get_broker_fee_definition(self.conn, def_id))


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestTaxBaseService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.tax_catalog_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import tax_catalog_svc

        return tax_catalog_svc

    def test_create_with_children(self):
        svc = self.import_svc()
        result = svc.create_tax_base(
            svc.TaxBaseCreate(
                ruleset_key="spain",
                name="Spain Savings",
                computation="progressive",
                categories=["capital_gains", "dividends"],
                rates=[{"from_amount": 0, "to_amount": 6000, "rate": 0.19}],
            )
        )
        self.assertGreater(result.id, 0)
        self.assertEqual(result.categories, ["capital_gains", "dividends"])
        self.assertEqual(len(result.rates), 1)
        self.assertAlmostEqual(result.rates[0].rate, 0.19)

    def test_put_replaces_children(self):
        svc = self.import_svc()
        created = svc.create_tax_base(
            svc.TaxBaseCreate(
                ruleset_key="spain",
                name="Spain",
                computation="flat",
                flat_rate=0.2,
                categories=["capital_gains"],
                rates=[],
            )
        )
        updated = svc.update_tax_base(
            created.id,
            svc.TaxBaseCreate(
                ruleset_key="spain",
                name="Spain v2",
                computation="progressive",
                categories=["dividends"],
                rates=[{"from_amount": 0, "to_amount": 6000, "rate": 0.21}],
            ),
        )
        self.assertEqual(updated.categories, ["dividends"])
        self.assertEqual(len(updated.rates), 1)
        self.assertAlmostEqual(updated.rates[0].rate, 0.21)
        self.assertEqual(updated.name, "Spain v2")

    def test_get_and_list(self):
        svc = self.import_svc()
        a = svc.create_tax_base(svc.TaxBaseCreate(ruleset_key="spain", name="Spain", computation="progressive"))
        svc.create_tax_base(svc.TaxBaseCreate(ruleset_key="japan", name="Japan", computation="flat"))
        self.assertEqual(len(svc.list_tax_bases()), 2)
        self.assertEqual(svc.get_tax_base(a.id).ruleset_key, "spain")

    def test_delete(self):
        svc = self.import_svc()
        created = svc.create_tax_base(svc.TaxBaseCreate(ruleset_key="spain", name="Spain", computation="progressive"))
        svc.delete_tax_base(created.id)
        with self.assertRaises(svc.TaxBaseNotFound):
            svc.get_tax_base(created.id)

    def test_validation_violations_rejected(self):
        from pydantic import ValidationError

        svc = self.import_svc()
        with self.assertRaises(ValidationError):
            svc.TaxBaseCreate(ruleset_key="x", name="X", computation="Band")
        with self.assertRaises(ValidationError):
            svc.TaxBaseCreate(ruleset_key="x", name="X", computation="progressive", categories=["real_estate"])


class TestTaxDefinitionService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.tax_catalog_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import tax_catalog_svc

        return tax_catalog_svc

    def test_create_get_list_update(self):
        svc = self.import_svc()
        created = svc.create_tax_definition(
            svc.TaxDefinitionCreate(slug="tasa_tobin", name="Tasa Tobin", ruleset_key="spain", rate=0.002)
        )
        self.assertEqual(svc.get_tax_definition(created.id).name, "Tasa Tobin")
        updated = svc.update_tax_definition(
            created.id, svc.TaxDefinitionCreate(slug="tasa_tobin", name="Tasa Tobin v2", rate=0.003)
        )
        self.assertEqual(updated.name, "Tasa Tobin v2")
        self.assertAlmostEqual(updated.rate, 0.003)
        self.assertEqual(len(svc.list_tax_definitions()), 1)

    def test_duplicate_slug_rejected(self):
        svc = self.import_svc()
        svc.create_tax_definition(svc.TaxDefinitionCreate(slug="tasa_tobin", name="A"))
        with self.assertRaises(svc.TaxDefinitionSlugTaken):
            svc.create_tax_definition(svc.TaxDefinitionCreate(slug="tasa_tobin", name="B"))

    def test_delete_in_use_rejected(self):
        svc = self.import_svc()
        created = svc.create_tax_definition(svc.TaxDefinitionCreate(slug="withholding", name="Withholding"))
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01T00:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (1, ?, 5.0, 'EUR')",
            (created.id,),
        )
        self.conn.commit()
        with self.assertRaises(svc.TaxDefinitionInUse):
            svc.delete_tax_definition(created.id)

    def test_delete_unreferenced_ok(self):
        svc = self.import_svc()
        created = svc.create_tax_definition(svc.TaxDefinitionCreate(slug="orphan", name="Orphan"))
        svc.delete_tax_definition(created.id)
        with self.assertRaises(svc.TaxDefinitionNotFound):
            svc.get_tax_definition(created.id)


class TestBrokerFeeDefinitionService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.tax_catalog_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import tax_catalog_svc

        return tax_catalog_svc

    def test_crud(self):
        svc = self.import_svc()
        created = svc.create_broker_fee_definition(svc.BrokerFeeDefinitionCreate(name="Commission"))
        self.assertEqual(svc.get_broker_fee_definition(created.id).name, "Commission")
        updated = svc.update_broker_fee_definition(created.id, svc.BrokerFeeDefinitionCreate(name="Commission EU"))
        self.assertEqual(updated.name, "Commission EU")
        self.assertEqual(len(svc.list_broker_fee_definitions()), 1)
        svc.delete_broker_fee_definition(created.id)
        with self.assertRaises(svc.BrokerFeeDefinitionNotFound):
            svc.get_broker_fee_definition(created.id)

    def test_delete_in_use_rejected(self):
        svc = self.import_svc()
        created = svc.create_broker_fee_definition(svc.BrokerFeeDefinitionCreate(name="Commission"))
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01T00:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO transaction_fees (transaction_id, broker_fee_definition_id, fee_type, nature, currency) VALUES (1, ?, 'BROKER', 'FIXED', 'EUR')",
            (created.id,),
        )
        self.conn.commit()
        with self.assertRaises(svc.BrokerFeeDefinitionInUse):
            svc.delete_broker_fee_definition(created.id)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


class TestTaxCatalogRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
        self.conn.commit()
        self.patcher = patch("services.tax_catalog_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_bases_crud_roundtrip(self):
        resp = client.get("/api/v1/tax-bases")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

        created = client.post(
            "/api/v1/tax-bases",
            json={
                "ruleset_key": "spain",
                "name": "Spain Savings",
                "computation": "progressive",
                "categories": ["capital_gains"],
                "rates": [{"from_amount": 0, "to_amount": 6000, "rate": 0.19}],
            },
        )
        self.assertEqual(created.status_code, 201)
        data = created.json()
        base_id = data["id"]
        self.assertEqual(data["categories"], ["capital_gains"])
        self.assertEqual(len(data["rates"]), 1)

        got = client.get(f"/api/v1/tax-bases/{base_id}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["name"], "Spain Savings")

        updated = client.put(
            f"/api/v1/tax-bases/{base_id}",
            json={
                "ruleset_key": "spain",
                "name": "Spain v2",
                "computation": "flat",
                "flat_rate": 0.2,
                "categories": [],
                "rates": [],
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["computation"], "flat")

        deleted = client.delete(f"/api/v1/tax-bases/{base_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(client.get(f"/api/v1/tax-bases/{base_id}").status_code, 404)

    def test_bases_invalid_computation_422(self):
        resp = client.post(
            "/api/v1/tax-bases",
            json={"ruleset_key": "x", "name": "X", "computation": "Band"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_definitions_crud_roundtrip(self):
        created = client.post(
            "/api/v1/tax-definitions",
            json={"slug": "tasa_tobin", "name": "Tasa Tobin", "ruleset_key": "spain", "rate": 0.002},
        )
        self.assertEqual(created.status_code, 201)
        def_id = created.json()["id"]

        got = client.get(f"/api/v1/tax-definitions/{def_id}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["slug"], "tasa_tobin")

        updated = client.put(
            f"/api/v1/tax-definitions/{def_id}",
            json={"slug": "tasa_tobin", "name": "Tasa Tobin v2", "rate": 0.003},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertAlmostEqual(updated.json()["rate"], 0.003)

        self.assertEqual(client.get("/api/v1/tax-definitions").status_code, 200)

        deleted = client.delete(f"/api/v1/tax-definitions/{def_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(client.get(f"/api/v1/tax-definitions/{def_id}").status_code, 404)

    def test_definition_duplicate_slug_409(self):
        client.post("/api/v1/tax-definitions", json={"slug": "tasa_tobin", "name": "A"})
        resp = client.post("/api/v1/tax-definitions", json={"slug": "tasa_tobin", "name": "B"})
        self.assertEqual(resp.status_code, 409)

    def test_definition_delete_in_use_422(self):
        created = client.post("/api/v1/tax-definitions", json={"slug": "withholding", "name": "Withholding"}).json()
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01T00:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (1, ?, 5.0, 'EUR')",
            (created["id"],),
        )
        self.conn.commit()
        resp = client.delete(f"/api/v1/tax-definitions/{created['id']}")
        self.assertEqual(resp.status_code, 422)

    def test_broker_fee_definitions_crud_roundtrip(self):
        created = client.post("/api/v1/broker-fee-definitions", json={"name": "Commission"})
        self.assertEqual(created.status_code, 201)
        def_id = created.json()["id"]

        got = client.get(f"/api/v1/broker-fee-definitions/{def_id}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["name"], "Commission")

        updated = client.put(f"/api/v1/broker-fee-definitions/{def_id}", json={"name": "Commission EU"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Commission EU")

        self.assertEqual(client.get("/api/v1/broker-fee-definitions").status_code, 200)

        deleted = client.delete(f"/api/v1/broker-fee-definitions/{def_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(client.get(f"/api/v1/broker-fee-definitions/{def_id}").status_code, 404)

    def test_broker_fee_delete_in_use_422(self):
        created = client.post("/api/v1/broker-fee-definitions", json={"name": "Commission"}).json()
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01T00:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO transaction_fees (transaction_id, broker_fee_definition_id, fee_type, nature, currency) VALUES (1, ?, 'BROKER', 'FIXED', 'EUR')",
            (created["id"],),
        )
        self.conn.commit()
        resp = client.delete(f"/api/v1/broker-fee-definitions/{created['id']}")
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
