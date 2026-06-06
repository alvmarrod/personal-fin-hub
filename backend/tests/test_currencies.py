import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.currencies import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


# Shared test app for route tests (no lifespan — no real DB access)
test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestCurrencyQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def test_get_distinct_codes_empty(self):
        self.assertEqual(queries.get_distinct_codes(self.conn), [])

    def test_get_distinct_codes_after_insert(self):
        queries.create_self_rate(self.conn, "EUR", datetime(2025, 1, 1))
        queries.create_self_rate(self.conn, "JPY", datetime(2025, 1, 1))
        self.assertEqual(queries.get_distinct_codes(self.conn), ["EUR", "JPY"])

    def test_get_distinct_codes_union(self):
        """Code that appears only as base_code should still be listed."""
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        self.assertIn("EUR", queries.get_distinct_codes(self.conn))
        self.assertIn("USD", queries.get_distinct_codes(self.conn))

    def test_code_exists(self):
        self.assertFalse(queries.code_exists(self.conn, "EUR"))
        queries.create_self_rate(self.conn, "EUR", datetime(2025, 1, 1))
        self.assertTrue(queries.code_exists(self.conn, "EUR"))

    def test_code_exists_only_as_base(self):
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        self.assertTrue(queries.code_exists(self.conn, "EUR"))

    def test_create_self_rate(self):
        ts = datetime(2025, 1, 1, 12, 0, 0)
        queries.create_self_rate(self.conn, "EUR", ts)
        row = self.conn.execute(
            "SELECT * FROM currencies WHERE code = ? AND base_code = ?",
            ("EUR", "EUR"),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["rate"], 1.0)

    def test_get_distinct_pairs_empty(self):
        self.assertEqual(queries.get_distinct_pairs(self.conn), [])

    def test_get_distinct_pairs(self):
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("JPY", "EUR", 160.0, datetime(2025, 1, 1)),
        )
        pairs = queries.get_distinct_pairs(self.conn)
        self.assertEqual(len(pairs), 2)
        self.assertIn(("JPY", "EUR"), pairs)
        self.assertIn(("USD", "EUR"), pairs)

    def test_get_distinct_pairs_filtered(self):
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("JPY", "EUR", 160.0, datetime(2025, 1, 1)),
        )
        pairs = queries.get_distinct_pairs(self.conn, "USD")
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0], ("USD", "EUR"))

    def test_pair_exists(self):
        self.assertFalse(queries.pair_exists(self.conn, "USD", "EUR"))
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        self.assertTrue(queries.pair_exists(self.conn, "USD", "EUR"))

    def test_insert_rate(self):
        ts = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts)
        row = self.conn.execute(
            "SELECT * FROM currencies WHERE code=? AND base_code=? AND timestamp=?",
            ("USD", "EUR", ts),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["rate"], 1.08)

    def test_get_latest_rate(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.05, ts1),
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, ts2),
        )
        row = queries.get_latest_rate(self.conn, "USD", "EUR")
        self.assertIsNotNone(row)
        self.assertEqual(row["rate"], 1.08)
        self.assertEqual(row["timestamp"], ts2.isoformat().replace("T", " "))

    def test_get_latest_rate_nonexistent(self):
        self.assertIsNone(queries.get_latest_rate(self.conn, "USD", "EUR"))

    def test_get_rate_at(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.05, ts1),
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, ts2),
        )
        row = queries.get_rate_at(self.conn, "USD", "EUR", datetime(2025, 3, 1))
        self.assertIsNotNone(row)
        self.assertEqual(row["rate"], 1.05)

    def test_get_rate_at_exact(self):
        ts = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, ts),
        )
        row = queries.get_rate_at(self.conn, "USD", "EUR", ts)
        self.assertIsNotNone(row)
        self.assertEqual(row["rate"], 1.08)

    def test_get_rate_history(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.05, ts1),
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, ts2),
        )
        rows = queries.get_rate_history(self.conn, "USD", "EUR")
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["rate"] for r in rows], [1.05, 1.08])

    def test_get_rate_history_empty(self):
        self.assertEqual(queries.get_rate_history(self.conn, "USD", "EUR"), [])

    def test_update_rate(self):
        ts = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, ts),
        )
        ok = queries.update_rate(self.conn, "USD", "EUR", ts, 1.10)
        self.assertTrue(ok)
        row = self.conn.execute(
            "SELECT rate FROM currencies WHERE code=? AND base_code=? AND timestamp=?",
            ("USD", "EUR", ts),
        ).fetchone()
        self.assertEqual(row["rate"], 1.10)

    def test_update_rate_nonexistent(self):
        ok = queries.update_rate(
            self.conn, "USD", "EUR", datetime(2025, 1, 1), 1.10
        )
        self.assertFalse(ok)

    def test_delete_pair(self):
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 1.08, datetime(2025, 1, 1)),
        )
        ok = queries.delete_pair(self.conn, "USD", "EUR")
        self.assertTrue(ok)
        self.assertFalse(queries.pair_exists(self.conn, "USD", "EUR"))

    def test_delete_pair_nonexistent(self):
        ok = queries.delete_pair(self.conn, "USD", "EUR")
        self.assertFalse(ok)

    def test_delete_pair_multiple_rows(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)", ("USD", "EUR", 1.05, ts1)
        )
        self.conn.execute(
            "INSERT INTO currencies VALUES (?, ?, ?, ?)", ("USD", "EUR", 1.08, ts2)
        )
        queries.delete_pair(self.conn, "USD", "EUR")
        self.assertEqual(len(queries.get_rate_history(self.conn, "USD", "EUR")), 0)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestCurrencyService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_service(self):
        from services import currency_svc
        return currency_svc

    def test_register_code(self):
        svc = self.import_service()
        result = svc.register_code("EUR")
        self.assertEqual(result.code, "EUR")
        self.assertEqual(result.base_code, "EUR")
        self.assertEqual(result.rate, 1.0)

    def test_register_code_duplicate(self):
        svc = self.import_service()
        svc.register_code("EUR")
        with self.assertRaises(svc.CurrencyError):
            svc.register_code("EUR")

    def test_get_codes_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.get_codes(), [])

    def test_get_codes(self):
        svc = self.import_service()
        svc.register_code("EUR")
        svc.register_code("USD")
        self.assertEqual(svc.get_codes(), ["EUR", "USD"])

    def test_get_pairs(self):
        svc = self.import_service()
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, datetime(2025, 1, 1))
        pairs = svc.get_pairs()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].code, "USD")
        self.assertEqual(pairs[0].base_code, "EUR")

    def test_get_pairs_filtered(self):
        svc = self.import_service()
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, datetime(2025, 1, 1))
        queries.insert_rate(self.conn, "JPY", "EUR", 160.0, datetime(2025, 1, 1))
        pairs = svc.get_pairs("USD")
        self.assertEqual(len(pairs), 1)

    def test_create_rate(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        result = svc.create_rate("USD", "EUR", 1.08, ts)
        self.assertEqual(result.rate, 1.08)
        self.assertFalse(result.inverted)

    def test_create_rate_reverse_pair_exists(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        with self.assertRaises(svc.ReversePairExists):
            svc.create_rate("EUR", "USD", 0.93, ts)

    def test_get_rate_latest(self):
        svc = self.import_service()
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.05, ts1)
        svc.create_rate("USD", "EUR", 1.08, ts2)
        result = svc.get_rate("USD", "EUR")
        self.assertEqual(result.rate, 1.08)

    def test_get_rate_at_time(self):
        svc = self.import_service()
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.05, ts1)
        svc.create_rate("USD", "EUR", 1.08, ts2)
        result = svc.get_rate("USD", "EUR", at=datetime(2025, 3, 1))
        self.assertEqual(result.rate, 1.05)

    def test_get_rate_auto_invert(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        # Query inverse direction
        result = svc.get_rate("EUR", "USD")
        self.assertAlmostEqual(result.rate, 1.0 / 1.08)
        self.assertTrue(result.inverted)

    def test_get_rate_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PairNotFound):
            svc.get_rate("EUR", "USD")

    def test_get_history(self):
        svc = self.import_service()
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.05, ts1)
        svc.create_rate("USD", "EUR", 1.08, ts2)
        history = svc.get_history("USD", "EUR")
        self.assertEqual(len(history), 2)
        self.assertEqual([h.rate for h in history], [1.05, 1.08])

    def test_get_history_auto_invert(self):
        svc = self.import_service()
        ts = datetime(2025, 1, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        history = svc.get_history("EUR", "USD")
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0].rate, 1.0 / 1.08)
        self.assertTrue(history[0].inverted)

    def test_get_history_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PairNotFound):
            svc.get_history("EUR", "USD")

    def test_update_rates(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        result = svc.update_rates("USD", "EUR", [ts], [1.10])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rate, 1.10)

    def test_update_rates_reverse_direction(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        with self.assertRaises(svc.ReversePairExists):
            svc.update_rates("EUR", "USD", [ts], [0.91])

    def test_update_rates_upserts_new_timestamp(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        svc.create_rate("USD", "EUR", 1.08, ts)
        ts2 = datetime(2025, 7, 1)
        result = svc.update_rates("USD", "EUR", [ts2], [1.10])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rate, 1.10)
        history = svc.get_history("USD", "EUR")
        self.assertEqual(len(history), 2)

    def test_delete_pair(self):
        svc = self.import_service()
        svc.create_rate("USD", "EUR", 1.08, datetime(2025, 6, 1))
        result = svc.delete_pair("USD", "EUR")
        self.assertTrue(result)

    def test_delete_pair_auto_invert(self):
        svc = self.import_service()
        svc.create_rate("USD", "EUR", 1.08, datetime(2025, 6, 1))
        result = svc.delete_pair("EUR", "USD")
        self.assertTrue(result)

    def test_delete_pair_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PairNotFound):
            svc.delete_pair("EUR", "USD")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestCurrencyRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    # GET /currencies -------------------------------------------------------
    def test_list_codes_empty(self):
        resp = client.get("/api/v1/currencies")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_codes(self):
        client.post("/api/v1/currencies", json={"code": "EUR"})
        resp = client.get("/api/v1/currencies")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("EUR", resp.json())

    # POST /currencies ------------------------------------------------------
    def test_register_code(self):
        resp = client.post("/api/v1/currencies", json={"code": "EUR"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["code"], "EUR")
        self.assertEqual(data["rate"], 1.0)

    def test_register_code_duplicate(self):
        client.post("/api/v1/currencies", json={"code": "EUR"})
        resp = client.post("/api/v1/currencies", json={"code": "EUR"})
        self.assertEqual(resp.status_code, 409)

    # GET /currencies/rates -------------------------------------------------
    def test_list_pairs_empty(self):
        resp = client.get("/api/v1/currencies/rates")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_pairs(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.get("/api/v1/currencies/rates")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0], {"code": "USD", "base_code": "EUR"})

    def test_list_pairs_filtered(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        client.post("/api/v1/currencies/rates", json={
            "code": "JPY", "base_code": "EUR", "rate": 160.0, "timestamp": ts,
        })
        resp = client.get("/api/v1/currencies/rates?code=JPY")
        self.assertEqual(len(resp.json()), 1)

    # POST /currencies/rates ------------------------------------------------
    def test_create_rate(self):
        ts = "2025-06-01T00:00:00"
        resp = client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["rate"], 1.08)
        self.assertFalse(data["inverted"])

    def test_create_rate_reverse_pair_conflict(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.post("/api/v1/currencies/rates", json={
            "code": "EUR", "base_code": "USD", "rate": 0.93, "timestamp": ts,
        })
        self.assertEqual(resp.status_code, 409)

    # GET /currencies/rates/{code}/{base_code} ------------------------------
    def test_get_latest_rate(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.get("/api/v1/currencies/rates/USD/EUR")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rate"], 1.08)

    def test_get_rate_at_time(self):
        ts1 = "2025-01-01T00:00:00"
        ts2 = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.05, "timestamp": ts1,
        })
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts2,
        })
        resp = client.get("/api/v1/currencies/rates/USD/EUR?at=2025-03-01T00:00:00")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rate"], 1.05)

    def test_get_rate_auto_inverted(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.get("/api/v1/currencies/rates/EUR/USD")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["rate"], 1.0 / 1.08)
        self.assertTrue(data["inverted"])

    def test_get_rate_not_found(self):
        resp = client.get("/api/v1/currencies/rates/EUR/USD")
        self.assertEqual(resp.status_code, 404)

    # GET /currencies/rates/{code}/{base_code}/history ----------------------
    def test_get_rate_history(self):
        ts1 = "2025-01-01T00:00:00"
        ts2 = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.05, "timestamp": ts1,
        })
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts2,
        })
        resp = client.get("/api/v1/currencies/rates/USD/EUR/history")
        self.assertEqual(resp.status_code, 200)
        rates = [r["rate"] for r in resp.json()]
        self.assertEqual(rates, [1.05, 1.08])

    def test_get_rate_history_auto_inverted(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.get("/api/v1/currencies/rates/EUR/USD/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertAlmostEqual(data[0]["rate"], 1.0 / 1.08)
        self.assertTrue(data[0]["inverted"])

    def test_get_rate_history_not_found(self):
        resp = client.get("/api/v1/currencies/rates/EUR/USD/history")
        self.assertEqual(resp.status_code, 404)

    # PUT /currencies/rates/{code}/{base_code} ------------------------------
    def test_bulk_update_rates(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.put("/api/v1/currencies/rates/USD/EUR", json={
            "timestamps": [ts],
            "rates": [1.10],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["rate"], 1.10)

    def test_bulk_update_multiple(self):
        ts1 = "2025-01-01T00:00:00"
        ts2 = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.05, "timestamp": ts1,
        })
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts2,
        })
        resp = client.put("/api/v1/currencies/rates/USD/EUR", json={
            "timestamps": [ts1, ts2],
            "rates": [1.06, 1.10],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r["rate"] for r in resp.json()], [1.06, 1.10])

    def test_bulk_update_length_mismatch(self):
        ts = "2025-06-01T00:00:00"
        resp = client.put("/api/v1/currencies/rates/USD/EUR", json={
            "timestamps": [ts],
            "rates": [1.10, 1.20],
        })
        self.assertEqual(resp.status_code, 422)

    def test_bulk_update_empty_arrays(self):
        resp = client.put("/api/v1/currencies/rates/USD/EUR", json={
            "timestamps": [],
            "rates": [],
        })
        self.assertEqual(resp.status_code, 422)

    def test_bulk_update_reverse_direction(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.put("/api/v1/currencies/rates/EUR/USD", json={
            "timestamps": [ts],
            "rates": [0.91],
        })
        self.assertEqual(resp.status_code, 409)

    def test_bulk_update_upserts_new_timestamp(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.put("/api/v1/currencies/rates/USD/EUR", json={
            "timestamps": ["2025-07-01T00:00:00"],
            "rates": [1.10],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["rate"], 1.10)

    # DELETE /currencies/rates/{code}/{base_code} ---------------------------
    def test_delete_pair(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.delete("/api/v1/currencies/rates/USD/EUR")
        self.assertEqual(resp.status_code, 204)

    def test_delete_pair_auto_invert(self):
        ts = "2025-06-01T00:00:00"
        client.post("/api/v1/currencies/rates", json={
            "code": "USD", "base_code": "EUR", "rate": 1.08, "timestamp": ts,
        })
        resp = client.delete("/api/v1/currencies/rates/EUR/USD")
        self.assertEqual(resp.status_code, 204)

    def test_delete_pair_not_found(self):
        resp = client.delete("/api/v1/currencies/rates/EUR/USD")
        self.assertEqual(resp.status_code, 404)

    def test_delete_code_with_market_asset_409(self):
        client.post("/api/v1/currencies", json={"code": "EUR"})
        self.conn.execute(
            "INSERT INTO market_assets (market_code, asset_type, currency_code) VALUES (?, ?, ?)",
            ("EUR.ASSET", "STOCK", "EUR"),
        )
        resp = client.delete("/api/v1/currencies/EUR")
        self.assertEqual(resp.status_code, 409)


if __name__ == "__main__":
    unittest.main()
