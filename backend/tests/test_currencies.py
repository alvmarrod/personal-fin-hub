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

    def test_get_codes_empty(self):
        svc = self.import_service()
        self.assertEqual(svc.get_codes(), [])

    def test_get_codes(self):
        svc = self.import_service()
        queries.create_self_rate(self.conn, "EUR", datetime(2025, 1, 1))
        queries.create_self_rate(self.conn, "USD", datetime(2025, 1, 1))
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

    def test_get_rate_latest(self):
        svc = self.import_service()
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.05, ts1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts2)
        result = svc.get_rate("USD", "EUR")
        self.assertEqual(result.rate, 1.08)

    def test_get_rate_at_time(self):
        svc = self.import_service()
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.05, ts1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts2)
        result = svc.get_rate("USD", "EUR", at=datetime(2025, 3, 1))
        self.assertEqual(result.rate, 1.05)

    def test_get_rate_auto_invert(self):
        svc = self.import_service()
        ts = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts)
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
        queries.insert_rate(self.conn, "USD", "EUR", 1.05, ts1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts2)
        history = svc.get_history("USD", "EUR")
        self.assertEqual(len(history), 2)
        self.assertEqual([h.rate for h in history], [1.05, 1.08])

    def test_get_history_auto_invert(self):
        svc = self.import_service()
        ts = datetime(2025, 1, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts)
        history = svc.get_history("EUR", "USD")
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0].rate, 1.0 / 1.08)
        self.assertTrue(history[0].inverted)

    def test_get_history_not_found(self):
        svc = self.import_service()
        with self.assertRaises(svc.PairNotFound):
            svc.get_history("EUR", "USD")


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
        queries.create_self_rate(self.conn, "EUR", datetime(2025, 1, 1))
        resp = client.get("/api/v1/currencies")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("EUR", resp.json())

    # GET /currencies/rates -------------------------------------------------
    def test_list_pairs_empty(self):
        resp = client.get("/api/v1/currencies/rates")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_pairs(self):
        now = datetime.now(timezone.utc)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, now)
        resp = client.get("/api/v1/currencies/rates")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0], {"code": "USD", "base_code": "EUR"})

    def test_list_pairs_filtered(self):
        now = datetime.now(timezone.utc)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, now)
        queries.insert_rate(self.conn, "JPY", "EUR", 160.0, now)
        resp = client.get("/api/v1/currencies/rates?code=JPY")
        self.assertEqual(len(resp.json()), 1)

    # GET /currencies/rates/{code}/{base_code} ------------------------------
    def test_get_latest_rate(self):
        now = datetime.now(timezone.utc)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, now)
        resp = client.get("/api/v1/currencies/rates/USD/EUR")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rate"], 1.08)

    def test_get_rate_at_time(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.05, ts1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts2)
        resp = client.get("/api/v1/currencies/rates/USD/EUR?at=2025-03-01T00:00:00")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rate"], 1.05)

    def test_get_rate_auto_inverted(self):
        now = datetime.now(timezone.utc)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, now)
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
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.05, ts1)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, ts2)
        resp = client.get("/api/v1/currencies/rates/USD/EUR/history")
        self.assertEqual(resp.status_code, 200)
        rates = [r["rate"] for r in resp.json()]
        self.assertEqual(rates, [1.05, 1.08])

    def test_get_rate_history_auto_inverted(self):
        now = datetime.now(timezone.utc)
        queries.insert_rate(self.conn, "USD", "EUR", 1.08, now)
        resp = client.get("/api/v1/currencies/rates/EUR/USD/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertAlmostEqual(data[0]["rate"], 1.0 / 1.08)
        self.assertTrue(data[0]["inverted"])

    def test_get_rate_history_not_found(self):
        resp = client.get("/api/v1/currencies/rates/EUR/USD/history")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
