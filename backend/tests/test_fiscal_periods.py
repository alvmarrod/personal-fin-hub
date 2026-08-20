import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from db.connection import ProfileScopedConnection
from routes.fiscal_periods import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> ProfileScopedConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False, factory=ProfileScopedConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestFiscalPeriodQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_create_returns_id(self):
        pid = queries.create_fiscal_period(self.conn, "spain", "2025-01-01")
        self.assertGreater(pid, 0)

    def test_create_and_get(self):
        pid = queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        row = queries.get_fiscal_period(self.conn, pid)
        assert row is not None
        self.assertEqual(row["rule_key"], "japan")
        self.assertEqual(row["start_date"], "2025-01-01")
        self.assertEqual(row["end_date"], "2025-12-31")

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_fiscal_period(self.conn, 999))

    def test_update(self):
        pid = queries.create_fiscal_period(self.conn, "spain", "2025-01-01")
        ok = queries.update_fiscal_period(self.conn, pid, "none", "2025-06-01", None)
        self.assertTrue(ok)
        row = queries.get_fiscal_period(self.conn, pid)
        assert row is not None
        self.assertEqual(row["rule_key"], "none")
        self.assertIsNone(row["end_date"])

    def test_delete(self):
        pid = queries.create_fiscal_period(self.conn, "spain", "2025-01-01")
        self.assertTrue(queries.delete_fiscal_period(self.conn, pid))
        self.assertIsNone(queries.get_fiscal_period(self.conn, pid))

    def test_get_fiscal_period_at(self):
        queries.create_fiscal_period(self.conn, "spain", "2025-01-01", "2025-06-30")
        queries.create_fiscal_period(self.conn, "japan", "2025-07-01", None)  # open-ended
        p1 = queries.get_fiscal_period_at(self.conn, "2025-03-01T10:00:00Z")
        p2 = queries.get_fiscal_period_at(self.conn, "2025-09-01T00:00:00Z")
        assert p1 is not None and p2 is not None
        self.assertEqual(p1["rule_key"], "spain")
        self.assertEqual(p2["rule_key"], "japan")
        self.assertIsNone(queries.get_fiscal_period_at(self.conn, "2024-12-31T00:00:00Z"))

    def test_resolve_fiscal_rule(self):
        queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        self.assertEqual(queries.resolve_fiscal_rule(self.conn, "2025-06-01T00:00:00Z"), "japan")
        self.assertIsNone(queries.resolve_fiscal_rule(self.conn, "2026-01-01T00:00:00Z"))


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestFiscalPeriodService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.fiscal_period_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import fiscal_period_svc

        return fiscal_period_svc

    def test_create(self):
        svc = self.import_service()
        body = svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01")
        result = svc.create(body)
        self.assertEqual(result.rule_key, "spain")
        self.assertIsNone(result.end_date)
        self.assertIsNotNone(result.id)

    def test_list_and_get(self):
        svc = self.import_service()
        svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-06-30"))
        svc.create(svc.FiscalPeriodCreate(rule_key="japan", start_date="2025-07-01"))
        self.assertEqual(len(svc.list_all()), 2)

    def test_update(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01"))
        result = svc.update(created.id, svc.FiscalPeriodCreate(rule_key="latest", start_date="2025-01-01"))
        self.assertEqual(result.rule_key, "latest")
        self.assertEqual(result.id, created.id)

    def test_delete(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01"))
        svc.delete(created.id)
        with self.assertRaises(svc.FiscalPeriodNotFound):
            svc.get(created.id)

    def test_create_overlap_rejected(self):
        svc = self.import_service()
        svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-06-30"))
        with self.assertRaises(svc.FiscalPeriodOverlap):
            svc.create(svc.FiscalPeriodCreate(rule_key="japan", start_date="2025-06-01", end_date="2025-12-31"))

    def test_open_ended_period_blocks_later_period(self):
        svc = self.import_service()
        svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01"))
        with self.assertRaises(svc.FiscalPeriodOverlap):
            svc.create(svc.FiscalPeriodCreate(rule_key="japan", start_date="2025-07-01"))

    def test_update_excluding_self_does_not_overlap(self):
        svc = self.import_service()
        created = svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-06-30"))
        result = svc.update(
            created.id, svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-08-01")
        )
        self.assertEqual(result.end_date.isoformat(), "2025-08-01")

    def test_update_overlap_with_other_rejected(self):
        svc = self.import_service()
        a = svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-06-30"))
        svc.create(svc.FiscalPeriodCreate(rule_key="japan", start_date="2025-07-01", end_date="2025-12-31"))
        with self.assertRaises(svc.FiscalPeriodOverlap):
            svc.update(a.id, svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01", end_date="2025-08-01"))

    def test_profile_isolation(self):
        svc = self.import_service()
        self.conn.profile_id = 1
        svc.create(svc.FiscalPeriodCreate(rule_key="spain", start_date="2025-01-01"))
        self.conn.profile_id = 2
        self.assertEqual(svc.list_all(), [])
        self.conn.profile_id = 1
        self.assertEqual(len(svc.list_all()), 1)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


class TestFiscalPeriodRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.fiscal_period_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/fiscal-periods")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/fiscal-periods", json={"rule_key": "spain", "start_date": "2025-01-01"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["rule_key"], "spain")
        self.assertEqual(data["start_date"], "2025-01-01")
        self.assertIsNone(data["end_date"])

    def test_create_invalid_rule(self):
        resp = client.post("/api/v1/fiscal-periods", json={"rule_key": "mars", "start_date": "2025-01-01"})
        self.assertEqual(resp.status_code, 422)

    def test_create_overlap_422(self):
        client.post(
            "/api/v1/fiscal-periods", json={"rule_key": "spain", "start_date": "2025-01-01", "end_date": "2025-06-30"}
        )
        resp = client.post("/api/v1/fiscal-periods", json={"rule_key": "japan", "start_date": "2025-06-01"})
        self.assertEqual(resp.status_code, 422)

    def test_get_and_delete(self):
        create_resp = client.post("/api/v1/fiscal-periods", json={"rule_key": "japan", "start_date": "2025-01-01"})
        pid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/fiscal-periods/{pid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rule_key"], "japan")
        resp = client.delete(f"/api/v1/fiscal-periods/{pid}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(client.get(f"/api/v1/fiscal-periods/{pid}").status_code, 404)

    def test_update(self):
        create_resp = client.post("/api/v1/fiscal-periods", json={"rule_key": "spain", "start_date": "2025-01-01"})
        pid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/fiscal-periods/{pid}", json={"rule_key": "none", "start_date": "2025-01-01"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rule_key"], "none")


# ---------------------------------------------------------------------------
# Snapshot + resolution integration
# ---------------------------------------------------------------------------


class TestFiscalRuleSnapshot(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Broker', 'BROKER')")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('USD', 'USD', 1.0, '2025-01-01T00:00:00')"
        )

    def tearDown(self):
        self.conn.close()

    def _create_sell(self, timestamp: str) -> int:
        return queries.create_transaction(
            self.conn,
            timestamp=timestamp,
            type_="INVESTMENT_SELL",
            entity_id=1,
            currency="USD",
            total_value=500.0,
            quantity=5,
            unit_price=100.0,
        )

    def _fiscal_rule(self, tx_id: int) -> str | None:
        row = queries.get_transaction(self.conn, tx_id)
        assert row is not None
        return row["fiscal_rule"]

    def test_sell_snapshots_rule_from_period(self):
        queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        tx_id = self._create_sell("2025-06-01T10:00:00Z")
        self.assertEqual(self._fiscal_rule(tx_id), "japan")

    def test_sell_without_period_snapshots_null(self):
        tx_id = self._create_sell("2025-06-01T10:00:00Z")
        self.assertIsNone(self._fiscal_rule(tx_id))

    def test_buy_never_snapshots_rule(self):
        queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        tx_id = queries.create_transaction(
            self.conn,
            timestamp="2025-06-01T10:00:00Z",
            type_="INVESTMENT_BUY",
            entity_id=1,
            currency="USD",
            total_value=1000.0,
        )
        self.assertIsNone(self._fiscal_rule(tx_id))

    def test_snapshot_frozen_when_period_deleted(self):
        period_id = queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        tx_id = self._create_sell("2025-06-01T10:00:00Z")
        queries.delete_fiscal_period(self.conn, period_id)
        self.assertEqual(self._fiscal_rule(tx_id), "japan")

    def test_snapshot_frozen_when_period_edited(self):
        period_id = queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        tx_id = self._create_sell("2025-06-01T10:00:00Z")
        queries.update_fiscal_period(self.conn, period_id, "spain", "2025-01-01", "2025-12-31")
        self.assertEqual(self._fiscal_rule(tx_id), "japan")

    def test_snapshot_re_resolves_on_timestamp_edit(self):
        queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        tx_id = self._create_sell("2025-06-01T10:00:00Z")
        queries.update_transaction(
            self.conn,
            tx_id,
            timestamp="2026-06-01T10:00:00Z",
            type_="INVESTMENT_SELL",
            entity_id=1,
            currency="USD",
            total_value=500.0,
        )
        self.assertIsNone(self._fiscal_rule(tx_id))


if __name__ == "__main__":
    unittest.main()
