import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.prices import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_market(conn: sqlite3.Connection, market_code: str = "AAPL.US") -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('USD', 'USD', 1.0, '2025-01-01')",
    )
    conn.execute(
        "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES (?, 'AAPL', 'STOCK', 'USD')",
        (market_code,),
    )


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------


class TestPriceQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_market(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_get_all_empty(self):
        self.assertEqual(queries.get_all_prices(self.conn), [])

    def test_create(self):
        price_id = queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25)
        row = queries.get_price(self.conn, price_id)
        assert row is not None
        assert row is not None
        self.assertIsNotNone(row)
        self.assertEqual(row["price"], 150.25)
        self.assertEqual(row["market_code"], "AAPL.US")

    def test_create_with_provider(self):
        price_id = queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25, "MARKET_API")
        row = queries.get_price(self.conn, price_id)
        assert row is not None
        self.assertEqual(row["provider"], "MARKET_API")

    def test_get_nonexistent(self):
        self.assertIsNone(queries.get_price(self.conn, 999))

    def test_get_prices_by_market(self):
        queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25)
        queries.create_price(self.conn, "AAPL.US", "2025-09-18T09:00:00Z", 151.00)
        rows = queries.get_prices_by_market(self.conn, "AAPL.US")
        self.assertEqual(len(rows), 2)

    def test_get_prices_by_market_empty(self):
        self.assertEqual(queries.get_prices_by_market(self.conn, "NOPE.NYSE"), [])

    def test_get_all_prices(self):
        queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25)
        queries.create_price(self.conn, "AAPL.US", "2025-09-18T09:00:00Z", 151.00)
        self.assertEqual(len(queries.get_all_prices(self.conn)), 2)

    def test_update(self):
        price_id = queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25)
        ok = queries.update_price(self.conn, price_id, "AAPL.US", "2025-09-17T09:00:00Z", 155.00)
        self.assertTrue(ok)
        row = queries.get_price(self.conn, price_id)
        assert row is not None
        self.assertEqual(row["price"], 155.00)

    def test_update_nonexistent(self):
        ok = queries.update_price(self.conn, 999, "AAPL.US", "2025-09-17T09:00:00Z", 100.0)
        self.assertFalse(ok)

    def test_delete(self):
        price_id = queries.create_price(self.conn, "AAPL.US", "2025-09-17T09:00:00Z", 150.25)
        ok = queries.delete_price(self.conn, price_id)
        self.assertTrue(ok)
        self.assertIsNone(queries.get_price(self.conn, price_id))

    def test_delete_nonexistent(self):
        ok = queries.delete_price(self.conn, 999)
        self.assertFalse(ok)

    def test_net_positions_include_inactive(self):
        from db.analytics_queries import get_net_positions_as_of

        self.conn.execute(
            "INSERT INTO entities (name, entity_type) VALUES ('Test', 'BROKER')",
        )
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES ('INACT.US', 'INACT', 'STOCK', 'USD')",
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active) VALUES ('INACT.US', 0)",
        )
        pa_id = self.conn.execute("SELECT id FROM portfolio_assets WHERE market_code = 'INACT.US'").fetchone()["id"]
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, portfolio_asset_id, quantity, total_value, currency) "
            "VALUES ('2025-06-01T10:00:00Z', 'INVESTMENT_BUY', 1, ?, 100, 10000, 'USD')",
            (pa_id,),
        )

        positions = get_net_positions_as_of(self.conn, "2025-07-01T00:00:00")
        codes = {p["market_code"] for p in positions}
        self.assertNotIn("INACT.US", codes)

        positions = get_net_positions_as_of(self.conn, "2025-07-01T00:00:00", include_inactive=True)
        codes = {p["market_code"] for p in positions}
        self.assertIn("INACT.US", codes)

    def test_net_positions_active_included(self):
        from db.analytics_queries import get_net_positions_as_of

        self.conn.execute(
            "INSERT INTO entities (name, entity_type) VALUES ('Test2', 'BANK')",
        )
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES ('ACTT.US', 'ACTT', 'STOCK', 'USD')",
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active) VALUES ('ACTT.US', 1)",
        )
        pa_id = self.conn.execute("SELECT id FROM portfolio_assets WHERE market_code = 'ACTT.US'").fetchone()["id"]
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, portfolio_asset_id, quantity, total_value, currency) "
            "VALUES ('2025-06-01T10:00:00Z', 'INVESTMENT_BUY', 1, ?, 100, 10000, 'USD')",
            (pa_id,),
        )

        positions = get_net_positions_as_of(self.conn, "2025-07-01T00:00:00")
        codes = {p["market_code"] for p in positions}
        self.assertIn("ACTT.US", codes)


# ---------------------------------------------------------------------------
# Endpoint-level tests (value-chart)
# ---------------------------------------------------------------------------


class TestPortfolioValueChart(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('USD', 'USD', 1.0, '2020-01-01')",
        )
        self.conn.execute(
            "INSERT INTO entities (name, entity_type) VALUES ('Test', 'BROKER')",
        )
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES ('AAPL.US', 'AAPL', 'STOCK', 'USD')",
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active) VALUES ('AAPL.US', 1)",
        )
        pa_id = self.conn.execute("SELECT id FROM portfolio_assets WHERE market_code = 'AAPL.US'").fetchone()["id"]
        self.conn.executemany(
            "INSERT INTO prices (market_code, timestamp, price) VALUES (?, ?, ?)",
            [
                ("AAPL.US", "2023-01-01T00:00:00Z", 150.0),
                ("AAPL.US", "2023-06-01T00:00:00Z", 160.0),
                ("AAPL.US", "2024-01-01T00:00:00Z", 170.0),
                ("AAPL.US", "2025-01-01T00:00:00Z", 180.0),
                ("AAPL.US", "2025-06-01T00:00:00Z", 190.0),
            ],
        )
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, portfolio_asset_id, quantity, total_value, currency) "
            "VALUES ('2023-01-01T10:00:00Z', 'INVESTMENT_BUY', 1, ?, 100, 10000, 'USD')",
            (pa_id,),
        )
        self.patcher = patch("routes.prices.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_all_returns_monthly_intervals(self):
        resp = client.get("/api/v1/prices/value-chart")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertIn("AAPL.US", data)
        points = data["AAPL.US"]
        self.assertGreater(len(points), 0)
        # With data from 2023+, default start is 2020, span > 2 years → monthly
        # Should have roughly (2025-2020)*12 = ~60 months worth
        self.assertGreater(len(points), 12)
        # Verify values increase with price
        values = [p["value"] for p in points]
        for i in range(1, len(values)):
            self.assertGreaterEqual(values[i], values[i - 1])

    def test_value_chart_applies_split_ratio(self):
        """Buy at 900, market price at 200 → 4.5:1 split detected → values multiplied by ~5."""
        # Create second asset with a split-affected buy
        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES ('SPLIT.US', 'SPLIT', 'STOCK', 'USD')",
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active) VALUES ('SPLIT.US', 1)",
        )
        pa_id = self.conn.execute("SELECT id FROM portfolio_assets WHERE market_code = 'SPLIT.US'").fetchone()["id"]
        # Buy 100 shares at 900 each (pre-split), market price was 200 (post-split adjusted)
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, portfolio_asset_id, quantity, unit_price, total_value, currency) "
            "VALUES ('2024-06-01T10:00:00Z', 'INVESTMENT_BUY', 1, ?, 100, 900.0, 90000, 'USD')",
            (pa_id,),
        )
        # Market prices at ~200 (post-split)
        self.conn.executemany(
            "INSERT INTO prices (market_code, timestamp, price) VALUES (?, ?, ?)",
            [
                ("SPLIT.US", "2024-06-01T00:00:00Z", 200.0),
                ("SPLIT.US", "2024-08-01T00:00:00Z", 210.0),
            ],
        )

        resp = client.get("/api/v1/prices/value-chart?start_date=2024-06-01&end_date=2024-08-01")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertIn("SPLIT.US", data)

        points = data["SPLIT.US"]
        # Without split adjustment: 100 * 200 = 20000, 100 * 210 = 21000
        # With 4.5→5:1 split: 20000*5=100000, 21000*5=105000
        self.assertGreater(len(points), 0)
        for p in points:
            # Value should be ~100k (split-adjusted), not 20k (raw)
            self.assertGreater(p["value"], 50000)

    def test_no_split_when_ratio_below_2(self):
        """Buy at 150, market at 100: ratio 1.5 → no split detected."""
        from db.analytics_queries import detect_stock_splits

        self.conn.execute(
            "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code) VALUES ('NORM.US', 'NORM', 'STOCK', 'USD')",
        )
        self.conn.execute(
            "INSERT INTO portfolio_assets (market_code, is_active) VALUES ('NORM.US', 1)",
        )
        pa_id = self.conn.execute("SELECT id FROM portfolio_assets WHERE market_code = 'NORM.US'").fetchone()["id"]
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, portfolio_asset_id, quantity, unit_price, total_value, currency) "
            "VALUES ('2025-01-01T10:00:00Z', 'INVESTMENT_BUY', 1, ?, 10, 150.0, 1500, 'USD')",
            (pa_id,),
        )
        self.conn.execute(
            "INSERT INTO prices (market_code, timestamp, price) VALUES ('NORM.US', '2025-01-01T00:00:00Z', 100.0)",
        )

        splits = detect_stock_splits(self.conn)
        codes = {s["market_code"] for s in splits}
        self.assertNotIn("NORM.US", codes)


# ---------------------------------------------------------------------------


class TestPriceService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_market(self.conn)
        self.patcher = patch("services.price_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import price_svc

        return price_svc

    def test_create(self):
        svc = self.import_service()
        body = svc.PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
        )
        result = svc.create(body)
        self.assertIsNotNone(result.id)
        self.assertEqual(result.price, 150.25)
        self.assertIsNone(result.provider)

    def test_create_with_provider(self):
        svc = self.import_service()
        body = svc.PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
            provider="MARKET_API",
        )
        result = svc.create(body)
        self.assertEqual(result.provider, "MARKET_API")

    def test_create_duplicate(self):
        svc = self.import_service()
        body = svc.PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
        )
        svc.create(body)
        with self.assertRaises(svc.PriceAlreadyExists):
            svc.create(body)

    def test_create_market_not_found(self):
        svc = self.import_service()
        body = svc.PriceCreate(
            market_code="NONEXISTENT",
            timestamp="2025-09-17T09:00:00Z",
            price=100.0,
        )
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.create(body)

    def test_get(self):
        svc = self.import_service()
        body = svc.PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
        )
        created = svc.create(body)
        result = svc.get(created.id)
        self.assertEqual(result.price, 150.25)

    def test_get_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PriceNotFound):
            svc.get(999)

    def test_list_all(self):
        svc = self.import_service()
        svc.create(svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=150.25))
        svc.create(svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-18T09:00:00Z", price=151.00))
        self.assertEqual(len(svc.list_all()), 2)

    def test_list_all_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(), [])

    def test_list_by_market(self):
        svc = self.import_service()
        svc.create(svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=150.25))
        svc.create(svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-18T09:00:00Z", price=151.00))
        self.assertEqual(len(svc.list_all(market_code="AAPL.US")), 2)

    def test_list_by_market_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.list_all(market_code="NONEXISTENT"), [])

    def test_update(self):
        svc = self.import_service()
        body = svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=150.25)
        created = svc.create(body)
        updated_body = svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=155.00)
        result = svc.update(created.id, updated_body)
        self.assertEqual(result.price, 155.00)

    def test_update_not_found(self):
        svc = self.import_service()
        body = svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=100.0)
        with self.assertRaises(svc.PriceNotFound):
            svc.update(999, body)

    def test_update_market_not_found(self):
        svc = self.import_service()
        body = svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=150.25)
        created = svc.create(body)
        bad_body = svc.PriceCreate(market_code="NONEXISTENT", timestamp="2025-09-17T09:00:00Z", price=100.0)
        with self.assertRaises(svc.MarketAssetNotFound):
            svc.update(created.id, bad_body)

    def test_delete(self):
        svc = self.import_service()
        body = svc.PriceCreate(market_code="AAPL.US", timestamp="2025-09-17T09:00:00Z", price=150.25)
        created = svc.create(body)
        svc.delete(created.id)
        with self.assertRaises(svc.PriceNotFound):
            svc.get(created.id)

    def test_delete_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PriceNotFound):
            svc.delete(999)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


class TestPriceRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_market(self.conn)
        self.patcher = patch("services.price_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_list_empty(self):
        resp = client.get("/api/v1/prices")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_create(self):
        resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["price"], 150.25)
        self.assertEqual(data["market_code"], "AAPL.US")
        self.assertIn("id", data)

    def test_create_with_provider(self):
        resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
                "provider": "MARKET_API",
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["provider"], "MARKET_API")

    def test_create_duplicate(self):
        client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 155.00,
            },
        )
        self.assertEqual(resp.status_code, 409)

    def test_create_market_not_found(self):
        resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "NONEXISTENT",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 100.0,
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_get(self):
        create_resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        price_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/prices/{price_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["price"], 150.25)

    def test_get_not_found(self):
        resp = client.get("/api/v1/prices/999")
        self.assertEqual(resp.status_code, 404)

    def test_list_by_market(self):
        client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-18T09:00:00Z",
                "price": 151.00,
            },
        )
        resp = client.get("/api/v1/prices?market_code=AAPL.US")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_update(self):
        create_resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        price_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/prices/{price_id}",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 155.00,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["price"], 155.00)

    def test_update_not_found(self):
        resp = client.put(
            "/api/v1/prices/999",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 100.0,
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete(self):
        create_resp = client.post(
            "/api/v1/prices",
            json={
                "market_code": "AAPL.US",
                "timestamp": "2025-09-17T09:00:00Z",
                "price": 150.25,
            },
        )
        price_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/prices/{price_id}")
        self.assertEqual(resp.status_code, 204)
        get_resp = client.get(f"/api/v1/prices/{price_id}")
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_not_found(self):
        resp = client.delete("/api/v1/prices/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
