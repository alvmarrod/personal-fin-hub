import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from models.enums import AssetClass, AssetType
from routes.market_assets import router

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


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestMarketAssetQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_market_assets(self.conn), [])

    def test_create(self):
        queries.create_market_asset(
            self.conn, "AAPL.US", "USD", "STOCK", ticker="AAPL",
        )
        row = queries.get_market_asset(self.conn, "AAPL.US")
        self.assertIsNotNone(row)
        self.assertEqual(row["ticker"], "AAPL")

    def test_create_with_all_fields(self):
        queries.create_market_asset(
            self.conn, "TEF.MC", "EUR", "STOCK", "TEF", "VI",
            "Telefonica", "Spanish telco", "BME",
        )
        row = queries.get_market_asset(self.conn, "TEF.MC")
        self.assertEqual(row["ticker"], "TEF")
        self.assertEqual(row["asset_class"], "VI")
        self.assertEqual(row["name"], "Telefonica")
        self.assertEqual(row["description"], "Spanish telco")
        self.assertEqual(row["exchange"], "BME")

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_market_asset(self.conn, "NONEXISTENT"))

    def test_get_all_returns_all(self):
        queries.create_market_asset(self.conn, "AAPL.US", "USD", "STOCK")
        queries.create_market_asset(self.conn, "VWCE.DE", "EUR", "ETF")
        self.assertEqual(len(queries.get_all_market_assets(self.conn)), 2)

    def test_update_returns_true(self):
        queries.create_market_asset(self.conn, "AAPL.US", "USD", "STOCK", name="Apple Inc.")
        ok = queries.update_market_asset(
            self.conn, "AAPL.US", "USD", "STOCK", name="Apple Inc. (Updated)"
        )
        self.assertTrue(ok)
        row = queries.get_market_asset(self.conn, "AAPL.US")
        self.assertEqual(row["name"], "Apple Inc. (Updated)")

    def test_update_nonexistent(self):
        ok = queries.update_market_asset(self.conn, "NOPE", "USD", "STOCK")
        self.assertFalse(ok)

    def test_delete_returns_true(self):
        queries.create_market_asset(self.conn, "AAPL.US", "USD", "STOCK")
        ok = queries.delete_market_asset(self.conn, "AAPL.US")
        self.assertTrue(ok)
        self.assertIsNone(queries.get_market_asset(self.conn, "AAPL.US"))

    def test_delete_nonexistent(self):
        ok = queries.delete_market_asset(self.conn, "NOPE")
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestMarketAssetService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        self.patcher = patch("services.market_asset_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import market_asset_svc
        return market_asset_svc

    def test_create(self):
        svc = self.import_service()
        body = svc.MarketAsset(
            market_code="AAPL.US", ticker="AAPL", asset_type=AssetType.STOCK,
            currency_code="USD",
        )
        result = svc.create(body)
        self.assertEqual(result.market_code, "AAPL.US")
        self.assertEqual(result.ticker, "AAPL")
        self.assertIsNone(result.name)

    def test_create_duplicate(self):
        svc = self.import_service()
        body = svc.MarketAsset(
            market_code="AAPL.US", asset_type=AssetType.STOCK, currency_code="USD",
        )
        svc.create(body)
        with self.assertRaises(svc.MarketAssetAlreadyExists):
            svc.create(body)

    def test_create_currency_not_found(self):
        svc = self.import_service()
        body = svc.MarketAsset(
            market_code="TEST", asset_type=AssetType.STOCK, currency_code="XXX",
        )
        with self.assertRaises(svc.CurrencyNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_service()
        body = svc.MarketAsset(
            market_code="VWCE.DE", asset_type=AssetType.ETF, currency_code="EUR",
        )
        svc.create(body)
        result = svc.get("VWCE.DE")
        self.assertEqual(result.asset_type, AssetType.ETF)

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.get("NOPE")

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.MarketAsset(market_code="A", asset_type=AssetType.STOCK, currency_code="USD"))
        svc.create(svc.MarketAsset(market_code="B", asset_type=AssetType.ETF, currency_code="EUR"))
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_update(self):
        svc = self.import_service()
        svc.create(svc.MarketAsset(market_code="AAPL.US", asset_type=AssetType.STOCK, currency_code="USD"))
        result = svc.update("AAPL.US", svc.MarketAsset(
            market_code="AAPL.US", asset_type=AssetType.STOCK, currency_code="USD",
            name="Apple Inc.",
        ))
        self.assertEqual(result.name, "Apple Inc.")

    def test_update_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.update("NOPE", svc.MarketAsset(
                market_code="NOPE", asset_type=AssetType.STOCK, currency_code="USD",
            ))

    def test_update_market_code_mismatch(self):
        svc = self.import_service()
        with self.assertRaises(svc.MarketAssetError):
            svc.update("CODE.A", svc.MarketAsset(
                market_code="CODE.B", asset_type=AssetType.STOCK, currency_code="USD",
            ))

    def test_update_currency_not_found(self):
        svc = self.import_service()
        svc.create(svc.MarketAsset(market_code="AAPL.US", asset_type=AssetType.STOCK, currency_code="USD"))
        with self.assertRaises(svc.CurrencyNotFound):
            svc.update("AAPL.US", svc.MarketAsset(
                market_code="AAPL.US", asset_type=AssetType.STOCK, currency_code="XXX",
            ))

    def test_delete(self):
        svc = self.import_service()
        svc.create(svc.MarketAsset(market_code="DEL", asset_type=AssetType.STOCK, currency_code="USD"))
        svc.delete("DEL")
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.get("DEL")

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.delete("NOPE")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestMarketAssetRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        self.patcher = patch("services.market_asset_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/market-assets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post("/api/v1/market-assets", json={
            "market_code": "AAPL.US",
            "ticker": "AAPL",
            "asset_type": "STOCK",
            "currency_code": "USD",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["market_code"], "AAPL.US")
        self.assertEqual(data["ticker"], "AAPL")

    def test_create_duplicate(self):
        client.post("/api/v1/market-assets", json={
            "market_code": "AAPL.US", "asset_type": "STOCK", "currency_code": "USD",
        })
        resp = client.post("/api/v1/market-assets", json={
            "market_code": "AAPL.US", "asset_type": "STOCK", "currency_code": "USD",
        })
        self.assertEqual(resp.status_code, 409)

    def test_create_currency_not_found(self):
        resp = client.post("/api/v1/market-assets", json={
            "market_code": "TEST", "asset_type": "STOCK", "currency_code": "XXX",
        })
        self.assertEqual(resp.status_code, 422)

    def test_get(self):
        client.post("/api/v1/market-assets", json={
            "market_code": "VWCE.DE", "asset_type": "ETF", "currency_code": "EUR",
        })
        resp = client.get("/api/v1/market-assets/VWCE.DE")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["asset_type"], "ETF")

    def test_get_not_found(self):
        resp = client.get("/api/v1/market-assets/NOPE")
        self.assertEqual(resp.status_code, 404)

    def test_list_multiple(self):
        client.post("/api/v1/market-assets", json={
            "market_code": "A", "asset_type": "STOCK", "currency_code": "USD",
        })
        client.post("/api/v1/market-assets", json={
            "market_code": "B", "asset_type": "ETF", "currency_code": "EUR",
        })
        resp = client.get("/api/v1/market-assets")
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        client.post("/api/v1/market-assets", json={
            "market_code": "AAPL.US", "asset_type": "STOCK", "currency_code": "USD",
        })
        resp = client.put("/api/v1/market-assets/AAPL.US", json={
            "market_code": "AAPL.US", "asset_type": "STOCK", "currency_code": "USD",
            "name": "Apple Inc.",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Apple Inc.")

    def test_update_not_found(self):
        resp = client.put("/api/v1/market-assets/NOPE", json={
            "market_code": "NOPE", "asset_type": "STOCK", "currency_code": "USD",
        })
        self.assertEqual(resp.status_code, 404)

    def test_update_market_code_mismatch(self):
        resp = client.put("/api/v1/market-assets/CODE.A", json={
            "market_code": "CODE.B", "asset_type": "STOCK", "currency_code": "USD",
        })
        self.assertEqual(resp.status_code, 422)

    def test_delete(self):
        client.post("/api/v1/market-assets", json={
            "market_code": "DEL", "asset_type": "STOCK", "currency_code": "USD",
        })
        resp = client.delete("/api/v1/market-assets/DEL")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get("/api/v1/market-assets/DEL")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/market-assets/NOPE")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
