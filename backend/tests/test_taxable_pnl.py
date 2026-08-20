import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import queries
from routes.analytics import router

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


def seed_currency(conn, code, rate=1.0, ts="2025-01-01T00:00:00Z"):
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)", (code, code, rate, ts)
    )


def seed_rate(conn, code, base, rate, ts):
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)", (code, base, rate, ts)
    )


def seed_entity(conn, eid=1):
    conn.execute("INSERT INTO entities (id, name, entity_type) VALUES (?, 'Broker', 'BROKER')", (eid,))


def seed_market_asset(conn):
    conn.execute(
        "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code, name) VALUES ('AAPL.US', 'AAPL', 'STOCK', 'USD', 'Apple')"
    )


def seed_portfolio_asset(conn, aid=1):
    conn.execute("INSERT INTO portfolio_assets (id, market_code) VALUES (?, 'AAPL.US')", (aid,))


def seed_buy(conn, entity_id, currency, total_value, aid, qty, unit_price, ts):
    conn.execute(
        "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, portfolio_asset_id, quantity, unit_price) VALUES (?, 'INVESTMENT_BUY', ?, ?, ?, ?, ?, ?)",
        (ts, entity_id, currency, total_value, aid, qty, unit_price),
    )


def seed_sell(conn, entity_id, currency, total_value, aid, qty, unit_price, ts, fiscal_rule=None, exemption_id=None):
    conn.execute(
        "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, portfolio_asset_id, quantity, unit_price, fiscal_rule, fiscal_exemption_id) VALUES (?, 'INVESTMENT_SELL', ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, entity_id, currency, total_value, aid, qty, unit_price, fiscal_rule, exemption_id),
    )


def seed_dividend(conn, entity_id, currency, total_value, ts, payment_date=None, exemption_id=None):
    conn.execute(
        "INSERT INTO transactions (timestamp, type, income_category, entity_id, currency, total_value, payment_date, fiscal_exemption_id) VALUES (?, 'INCOME', 'dividends', ?, ?, ?, ?, ?)",
        (ts, entity_id, currency, total_value, payment_date or ts, exemption_id),
    )


class TestTaxablePnl(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.analytics_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.patcher2 = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        self.conn.close()

    def import_svc(self):
        from services import analytics_svc

        return analytics_svc

    def _seed_sell_scenario(
        self, exemption_id=None, rule=None, sell_total=880.0, sell_price=110.0, sell_ts="2025-06-15T00:00:00Z"
    ):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn, 1)
        seed_buy(self.conn, 1, "USD", 1000.0, 1, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_sell(
            self.conn, 1, "USD", sell_total, 1, 8, sell_price, sell_ts, fiscal_rule=rule, exemption_id=exemption_id
        )

    def test_basic_gains_and_dividends(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z")
        seed_rate(self.conn, "USD", "EUR", 0.85, "2025-08-01T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        self.assertEqual(result.ruleset, "spain")
        self.assertEqual(len(result.fiscal_years), 1)
        year = result.fiscal_years[0]
        self.assertEqual(year.fiscal_year, 2025)
        self.assertAlmostEqual(year.realized_gains_taxable, 72.0, places=4)
        self.assertAlmostEqual(year.dividends_taxable, 170.0, places=4)
        self.assertAlmostEqual(year.total_taxable, 242.0, places=4)
        self.assertEqual(year.num_sells, 1)
        self.assertEqual(year.num_dividends, 1)
        self.assertAlmostEqual(result.total_taxable, 242.0, places=4)

    def test_fiscal_year_grouping(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        seed_buy(self.conn, 1, "USD", 500.0, 1, 5, 100.0, "2025-12-01T00:00:00Z")
        seed_sell(self.conn, 1, "USD", 600.0, 1, 5, 120.0, "2026-01-15T00:00:00Z")
        seed_rate(self.conn, "USD", "EUR", 0.8, "2026-01-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        self.assertEqual({y.fiscal_year for y in result.fiscal_years}, {2025, 2026})
        by_year = {y.fiscal_year: y for y in result.fiscal_years}
        self.assertEqual(by_year[2025].num_sells, 1)
        self.assertEqual(by_year[2026].num_sells, 1)

    def test_ruleset_param_drives_fallback_rule(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-01-01T00:00:00Z")
        seed_rate(self.conn, "USD", "EUR", 0.8, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES", "japan")
        self.assertEqual(result.ruleset, "japan")
        self.assertAlmostEqual(result.fiscal_years[0].realized_gains_taxable, -16.0, places=4)

    def test_exemption_rate_reduces_taxable(self):
        eid = queries.create_fiscal_exemption(self.conn, "ISA", exemption_rate=50)
        self._seed_sell_scenario(exemption_id=eid)
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        self.assertAlmostEqual(result.fiscal_years[0].realized_gains_taxable, 36.0, places=4)

    def test_exemption_full(self):
        eid = queries.create_fiscal_exemption(self.conn, "NISA", exemption_rate=100)
        self._seed_sell_scenario(exemption_id=eid)
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        self.assertAlmostEqual(result.fiscal_years[0].realized_gains_taxable, 0.0, places=4)

    def test_loss_passthrough(self):
        eid = queries.create_fiscal_exemption(self.conn, "ISA", exemption_rate=100)
        self._seed_sell_scenario(exemption_id=eid, sell_total=400.0, sell_price=50.0)
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        self.assertAlmostEqual(result.fiscal_years[0].realized_gains_taxable, -360.0, places=4)

    def test_exemption_fixed_amount(self):
        eid = queries.create_fiscal_exemption(self.conn, "ISA", exemption_rate=100, exemption_amount=30)
        self._seed_sell_scenario(exemption_id=eid)
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        # gain 80 * 0.9 = 72; exempt min(72, 100% of 72 + 30) = 72 → taxable 0
        self.assertAlmostEqual(result.fiscal_years[0].realized_gains_taxable, 0.0, places=4)

    def test_dividend_exemption(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        eid = queries.create_fiscal_exemption(self.conn, "ISA", exemption_rate=50)
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z", exemption_id=eid)
        seed_rate(self.conn, "USD", "EUR", 0.85, "2025-08-01T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl("EUR", "es-ES")
        # dividend 200*0.85 = 170; 50% exempt → 85
        self.assertAlmostEqual(result.fiscal_years[0].dividends_taxable, 85.0, places=4)


class TestTaxablePnlRoute(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.analytics_svc.get_db", return_value=self.conn)
        self.patcher.start()
        self.patcher2 = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        self.conn.close()

    def test_route_shape(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        resp = client.get("/api/v1/analytics/taxable-pnl?display_currency=EUR&locale=es-ES")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ruleset"], "spain")
        self.assertEqual(data["display_currency"], "EUR")
        self.assertIn("fiscal_years", data)
        self.assertIn("total_taxable", data)
        self.assertIn("rate_fallbacks", data)


if __name__ == "__main__":
    unittest.main()
