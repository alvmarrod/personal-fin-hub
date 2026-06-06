import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import DcaStatus, DistributionType, Layer, TrackingMode
from routes.portfolio_assets import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_currency(conn: sqlite3.Connection, code: str) -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, 1.0, '2025-01-01')",
        (code, code),
    )


def seed_market_asset(conn: sqlite3.Connection, code: str = "AAPL.US") -> None:
    conn.execute(
        "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES (?, ?, ?, ?)",
        (code, "AAPL", "STOCK", "USD"),
    )


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestPortfolioAssetQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_portfolio_assets(self.conn), [])

    def test_create_returns_id(self):
        aid = queries.create_portfolio_asset(self.conn, "AAPL.US")
        self.assertIsInstance(aid, int)
        self.assertGreater(aid, 0)

    def test_create_with_all_fields(self):
        aid = queries.create_portfolio_asset(
            self.conn, "AAPL.US", "distribution", "ongoing", "core", True,
            20.0, 0.5, "auto", None, True, "2025-01-01", "2024-06-01", "My core position",
        )
        row = queries.get_portfolio_asset(self.conn, aid)
        self.assertEqual(row["market_code"], "AAPL.US")
        self.assertEqual(row["distribution_type"], "distribution")
        self.assertEqual(row["dca_status"], "ongoing")
        self.assertEqual(row["layer"], "core")
        self.assertEqual(row["tactic"], 1)
        self.assertEqual(row["desired_weight"], 20.0)
        self.assertEqual(row["ter"], 0.5)
        self.assertEqual(row["notes"], "My core position")

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_portfolio_asset(self.conn, 999))

    def test_get_all_returns_all(self):
        queries.create_portfolio_asset(self.conn, "AAPL.US")
        queries.create_portfolio_asset(self.conn, "AAPL.US")
        self.assertEqual(len(queries.get_all_portfolio_assets(self.conn)), 2)

    def test_get_by_market(self):
        queries.create_portfolio_asset(self.conn, "AAPL.US")
        queries.create_portfolio_asset(self.conn, "AAPL.US")
        result = queries.get_portfolio_assets_by_market(self.conn, "AAPL.US")
        self.assertEqual(len(result), 2)

    def test_get_by_market_empty(self):
        self.assertEqual(queries.get_portfolio_assets_by_market(self.conn, "NOPE"), [])

    def test_update_returns_true(self):
        aid = queries.create_portfolio_asset(self.conn, "AAPL.US", notes="Old note")
        ok = queries.update_portfolio_asset(self.conn, aid, "AAPL.US", notes="New note")
        self.assertTrue(ok)
        row = queries.get_portfolio_asset(self.conn, aid)
        self.assertEqual(row["notes"], "New note")

    def test_update_nonexistent(self):
        ok = queries.update_portfolio_asset(self.conn, 999, "AAPL.US")
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        aid = queries.create_portfolio_asset(self.conn, "AAPL.US")
        ok = queries.delete_portfolio_asset(self.conn, aid)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_portfolio_asset(self.conn, aid))

    def test_delete_nonexistent(self):
        ok = queries.delete_portfolio_asset(self.conn, 999)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestPortfolioAssetService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        self.patcher = patch("services.portfolio_asset_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import portfolio_asset_svc
        return portfolio_asset_svc

    def test_create_minimal(self):
        svc = self.import_service()
        body = svc.PortfolioAssetCreate(market_code="AAPL.US")
        result = svc.create(body)
        self.assertEqual(result.market_code, "AAPL.US")
        self.assertIsNotNone(result.id)
        self.assertTrue(result.is_active)
        self.assertEqual(result.tracking_mode, TrackingMode.AUTO)

    def test_create_with_all_fields(self):
        svc = self.import_service()
        body = svc.PortfolioAssetCreate(
            market_code="AAPL.US",
            distribution_type=DistributionType.DISTRIBUTION,
            dca_status=DcaStatus.ONGOING,
            layer=Layer.CORE,
            tactic=True,
            desired_weight=20.0,
            ter=0.5,
            tracking_mode=TrackingMode.MANUAL,
            current_value_manual=10000.0,
            is_active=False,
            closing_date=date(2025, 12, 31),
            purchase_date=date(2024, 6, 1),
            notes="Test",
        )
        result = svc.create(body)
        self.assertEqual(result.distribution_type, DistributionType.DISTRIBUTION)
        self.assertEqual(result.layer, Layer.CORE)
        self.assertEqual(result.tracking_mode, TrackingMode.MANUAL)
        self.assertEqual(result.current_value_manual, 10000.0)
        self.assertFalse(result.is_active)

    def test_create_market_asset_not_found(self):
        svc = self.import_service()
        body = svc.PortfolioAssetCreate(market_code="NONEXISTENT")
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_service()
        created = svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        result = svc.get(created.id)
        self.assertEqual(result.market_code, "AAPL.US")

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PortfolioAssetNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_service()
        created = svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        result = svc.update(created.id, svc.PortfolioAssetCreate(
            market_code="AAPL.US", notes="Updated", desired_weight=30.0,
        ))
        self.assertEqual(result.notes, "Updated")
        self.assertEqual(result.desired_weight, 30.0)

    def test_update_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PortfolioAssetNotFound):
            svc.update(999, svc.PortfolioAssetCreate(market_code="AAPL.US"))

    def test_update_market_asset_not_found(self):
        svc = self.import_service()
        created = svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.update(created.id, svc.PortfolioAssetCreate(market_code="NONEXISTENT"))

    def test_delete(self):
        svc = self.import_service()
        created = svc.create(svc.PortfolioAssetCreate(market_code="AAPL.US"))
        svc.delete(created.id)
        with self.assertRaises(svc.PortfolioAssetNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PortfolioAssetNotFound):
            svc.delete(999)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestPortfolioAssetRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        self.patcher = patch("services.portfolio_asset_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/portfolio-assets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/portfolio-assets", json={
            "market_code": "AAPL.US",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["market_code"], "AAPL.US")
        self.assertIn("id", data)
        self.assertTrue(data["is_active"])

    def test_create_with_all_fields(self):
        resp = client.post("/api/v1/portfolio-assets", json={
            "market_code": "AAPL.US",
            "distribution_type": "distribution",
            "dca_status": "ongoing",
            "layer": "core",
            "tactic": True,
            "desired_weight": 20.0,
            "ter": 0.5,
            "tracking_mode": "manual",
            "current_value_manual": 10000.0,
            "is_active": False,
            "closing_date": "2025-12-31",
            "purchase_date": "2024-06-01",
            "notes": "Test",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["distribution_type"], "distribution")
        self.assertEqual(data["current_value_manual"], 10000.0)
        self.assertFalse(data["is_active"])

    def test_create_market_asset_not_found(self):
        resp = client.post("/api/v1/portfolio-assets", json={
            "market_code": "NONEXISTENT",
        })
        self.assertEqual(resp.status_code, 422)

    def test_get(self):
        create_resp = client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        aid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/portfolio-assets/{aid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["market_code"], "AAPL.US")

    def test_get_not_found(self):
        resp = client.get("/api/v1/portfolio-assets/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        resp = client.get("/api/v1/portfolio-assets")
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        create_resp = client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        aid = create_resp.json()["id"]
        resp = client.put(f"/api/v1/portfolio-assets/{aid}", json={
            "market_code": "AAPL.US",
            "notes": "Updated",
            "desired_weight": 30.0,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["notes"], "Updated")

    def test_update_not_found(self):
        resp = client.put("/api/v1/portfolio-assets/999", json={"market_code": "AAPL.US"})
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        aid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/portfolio-assets/{aid}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/portfolio-assets/{aid}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/portfolio-assets/999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_with_transaction_409(self):
        create_resp = client.post("/api/v1/portfolio-assets", json={"market_code": "AAPL.US"})
        aid = create_resp.json()["id"]
        cursor = self.conn.execute(
            "INSERT INTO entities (name, entity_type) VALUES (?, ?)",
            ("Test", "BROKER"),
        )
        eid = cursor.lastrowid
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, portfolio_asset_id) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-01T00:00:00", "INVESTMENT_BUY", eid, "USD", aid),
        )
        resp = client.delete(f"/api/v1/portfolio-assets/{aid}")
        self.assertEqual(resp.status_code, 409)


if __name__ == "__main__":
    unittest.main()
