import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_currency(conn: sqlite3.Connection, code: str, rate: float = 1.0) -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
        (code, code, rate, "2025-01-01T00:00:00Z"),
    )


def seed_entity(conn: sqlite3.Connection, eid: int = 1, name: str = "Broker") -> None:
    conn.execute(
        "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
        (eid, name, "BROKER"),
    )


def seed_market_asset(
    conn: sqlite3.Connection,
    code: str = "AAPL.US",
    ticker: str = "AAPL",
    asset_type: str = "STOCK",
    currency_code: str = "USD",
    name: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code, name) VALUES (?, ?, ?, ?, ?)",
        (code, ticker, asset_type, currency_code, name or code),
    )


def seed_portfolio_asset(
    conn: sqlite3.Connection,
    market_code: str = "AAPL.US",
    layer: str | None = None,
    tracking_mode: str = "auto",
    current_value_manual: float | None = None,
    is_active: int = 1,
    aid: int | None = None,
) -> int:
    if aid is not None:
        conn.execute(
            "INSERT INTO portfolio_assets (id, market_code, layer, tracking_mode, current_value_manual, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (aid, market_code, layer, tracking_mode, current_value_manual, is_active),
        )
        return aid
    conn.execute(
        "INSERT INTO portfolio_assets (market_code, layer, tracking_mode, current_value_manual, is_active) VALUES (?, ?, ?, ?, ?)",
        (market_code, layer, tracking_mode, current_value_manual, is_active),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_price(
    conn: sqlite3.Connection,
    market_code: str,
    price: float,
    timestamp: str = "2025-06-01T12:00:00Z",
) -> None:
    conn.execute(
        "INSERT INTO prices (market_code, timestamp, price) VALUES (?, ?, ?)",
        (market_code, timestamp, price),
    )


def seed_dividend_tx(
    conn: sqlite3.Connection,
    entity_id: int,
    currency: str,
    total_value: float,
    portfolio_asset_id: int | None = None,
    timestamp: str = "2025-03-15T10:00:00Z",
) -> None:
    conn.execute(
        "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, portfolio_asset_id) VALUES (?, 'DIVIDEND', ?, ?, ?, ?)",
        (timestamp, entity_id, currency, total_value, portfolio_asset_id),
    )


def seed_fee(
    conn: sqlite3.Connection,
    transaction_id: int,
    fee_type: str = "BROKER",
    nature: str = "FIXED",
    fixed_amount: float = 5.0,
    percentage: float = 0.0,
    currency: str = "USD",
) -> int:
    conn.execute(
        "INSERT INTO transaction_fees (transaction_id, fee_type, nature, fixed_amount, percentage, currency) VALUES (?, ?, ?, ?, ?, ?)",
        (transaction_id, fee_type, nature, fixed_amount, percentage, currency),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_tax(
    conn: sqlite3.Connection,
    transaction_id: int,
    tax_type: str = "WITHHOLDING",
    tax_amount: float = 10.0,
    currency: str = "USD",
    tax_rate: float | None = 15.0,
) -> int:
    conn.execute(
        "INSERT INTO transaction_taxes (transaction_id, tax_type, tax_rate, tax_amount, currency) VALUES (?, ?, ?, ?, ?)",
        (transaction_id, tax_type, tax_rate, tax_amount, currency),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_tx(
    conn: sqlite3.Connection,
    type_: str,
    entity_id: int,
    currency: str,
    total_value: float,
    portfolio_asset_id: int | None = None,
    quantity: float | None = None,
    unit_price: float | None = None,
    timestamp: str = "2025-01-15T10:00:00Z",
) -> None:
    conn.execute(
        "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, portfolio_asset_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, type_, entity_id, currency, total_value, portfolio_asset_id, quantity, unit_price),
    )


def seed_full_scenario(conn: sqlite3.Connection) -> dict:
    seed_currency(conn, "USD")
    seed_currency(conn, "EUR")
    seed_entity(conn, 1)
    seed_market_asset(conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple Inc.")
    seed_market_asset(conn, "VWCE.MC", "VWCE", "ETF", "EUR", "FTSE All-World")
    seed_market_asset(conn, "BTC", "BTC", "CRYPTO", "USD", "Bitcoin")
    aid1 = seed_portfolio_asset(conn, "AAPL.US", "core", "auto", aid=1)
    aid2 = seed_portfolio_asset(conn, "VWCE.MC", "core", "auto", aid=2)
    aid3 = seed_portfolio_asset(conn, "BTC", "satellite", "auto", aid=3)
    aid4 = seed_portfolio_asset(conn, "AAPL.US", "reserve", "manual", 5000.0, aid=4)
    seed_price(conn, "AAPL.US", 200.0)
    seed_price(conn, "VWCE.MC", 120.0)
    seed_price(conn, "BTC", 60000.0)
    seed_tx(conn, "INVESTMENT_BUY", 1, "USD", 1500.0, aid1, 10, 150.0)
    seed_tx(conn, "INVESTMENT_BUY", 1, "EUR", 1000.0, aid2, 10, 100.0)
    seed_tx(conn, "INVESTMENT_BUY", 1, "USD", 50000.0, aid3, 1, 50000.0)
    seed_tx(conn, "INVESTMENT_SELL", 1, "USD", 500.0, aid1, 2, 250.0)
    seed_tx(conn, "MONEY_IN", 1, "USD", 10000.0)
    seed_tx(conn, "MONEY_OUT", 1, "USD", 2000.0)
    return {"aid1": aid1, "aid2": aid2, "aid3": aid3, "aid4": aid4}


# ---------------------------------------------------------------------------
# Query-level tests
# ---------------------------------------------------------------------------

class TestAnalyticsQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def tearDown(self):
        self.conn.close()

    def import_q(self):
        from db import analytics_queries
        return analytics_queries

    def test_holdings_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_holdings_raw(self.conn), [])

    def test_holdings_raw_active_only(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn, is_active=0)
        q = self.import_q()
        self.assertEqual(q.get_holdings_raw(self.conn), [])

    def test_holdings_raw_basic(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_holdings_raw(self.conn)
        self.assertEqual(len(rows), 4)
        row1 = next(r for r in rows if r["portfolio_asset_id"] == 1)
        self.assertEqual(row1["total_bought_qty"], 10.0)
        self.assertEqual(row1["total_cost"], 1500.0)
        self.assertEqual(row1["total_sold_qty"], 2.0)
        self.assertEqual(row1["total_proceeds"], 500.0)

    def test_holdings_raw_no_transactions(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn)
        q = self.import_q()
        rows = q.get_holdings_raw(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_bought_qty"], 0.0)
        self.assertEqual(rows[0]["total_cost"], 0.0)

    def test_latest_prices_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_latest_prices(self.conn), [])

    def test_latest_prices_single(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        seed_price(self.conn, "AAPL.US", 200.0)
        q = self.import_q()
        prices = q.get_latest_prices(self.conn)
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0]["market_code"], "AAPL.US")
        self.assertEqual(prices[0]["price"], 200.0)

    def test_latest_prices_most_recent(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        seed_price(self.conn, "AAPL.US", 100.0, "2025-01-01T00:00:00Z")
        seed_price(self.conn, "AAPL.US", 200.0, "2025-06-01T00:00:00Z")
        q = self.import_q()
        prices = q.get_latest_prices(self.conn)
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0]["price"], 200.0)

    def test_latest_prices_multiple_codes(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        prices = q.get_latest_prices(self.conn)
        self.assertEqual(len(prices), 3)
        codes = {p["market_code"] for p in prices}
        self.assertEqual(codes, {"AAPL.US", "VWCE.MC", "BTC"})

    def test_cash_balance_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_cash_balance(self.conn), 0.0)

    def test_cash_balance_money_in_out(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_tx(self.conn, "MONEY_IN", 1, "USD", 10000.0)
        seed_tx(self.conn, "MONEY_OUT", 1, "USD", 3000.0)
        q = self.import_q()
        self.assertEqual(q.get_cash_balance(self.conn), 7000.0)

    def test_cash_balance_with_buys_and_sells(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        cash = q.get_cash_balance(self.conn)
        expected = 10000.0 - 2000.0 + 500.0 - 1500.0 - 1000.0 - 50000.0
        self.assertEqual(cash, expected)


    def test_cash_flow_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_cash_flow(self.conn, "month"), [])

    def test_cash_flow_basic(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow(self.conn, "month")
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIn("period", r)
            self.assertIn("type", r)

    def test_cash_flow_with_date_filter(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow(self.conn, "month", start="2025-06-01")
        self.assertEqual(rows, [])

    def test_cash_flow_group_by_year(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow(self.conn, "year")
        self.assertGreater(len(rows), 0)
        self.assertEqual(len(set(r["period"] for r in rows)), 1)

    def test_dividends_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_dividends(self.conn), [])

    def test_dividends_basic(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        q = self.import_q()
        rows = q.get_dividends(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_dividends"], 50.0)

    def test_dividends_with_date_filter(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        q = self.import_q()
        rows = q.get_dividends(self.conn, end="2025-01-01")
        self.assertEqual(rows, [])

    def test_fees_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_fees_raw(self.conn), [])

    def test_fees_raw_basic(self):
        seed_full_scenario(self.conn)
        tx_ids = [r["id"] for r in self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY'").fetchall()]
        seed_fee(self.conn, tx_ids[0])
        q = self.import_q()
        rows = q.get_fees_raw(self.conn)
        self.assertEqual(len(rows), 1)

    def test_taxes_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_taxes_raw(self.conn), [])

    def test_taxes_raw_basic(self):
        seed_full_scenario(self.conn)
        tx_ids = [r["id"] for r in self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY'").fetchall()]
        seed_tax(self.conn, tx_ids[0])
        q = self.import_q()
        rows = q.get_taxes_raw(self.conn)
        self.assertEqual(len(rows), 1)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.analytics_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def import_svc(self):
        from services import analytics_svc
        return analytics_svc

    def test_dashboard_empty(self):
        svc = self.import_svc()
        d = svc.get_dashboard()
        self.assertEqual(d.total_portfolio_value, 0.0)
        self.assertEqual(d.total_invested, 0.0)
        self.assertEqual(d.cash_balance, 0.0)
        self.assertEqual(d.num_holdings, 0)

    def test_dashboard_with_data(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        d = svc.get_dashboard()
        self.assertEqual(d.num_holdings, 4)
        self.assertGreater(d.total_portfolio_value, 0)
        self.assertGreater(d.total_invested, 0)

    def test_dashboard_cash_balance(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        d = svc.get_dashboard()
        self.assertEqual(d.cash_balance, -44000.0)

    def test_holdings_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.get_holdings(), [])

    def test_holdings_basic(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        holdings = svc.get_holdings()
        self.assertEqual(len(holdings), 4)

    def test_holdings_net_quantity(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        holdings = svc.get_holdings()
        aapl = next(h for h in holdings if h.market_code == "AAPL.US" and h.layer.name == "CORE")
        self.assertEqual(aapl.net_quantity, 8.0)

    def test_holdings_manual_tracking(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        holdings = svc.get_holdings()
        manual = next(h for h in holdings if h.tracking_mode.name == "MANUAL")
        self.assertEqual(manual.current_value, 5000.0)

    def test_holdings_no_price_auto(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn, "NOPRICE.US")
        seed_portfolio_asset(self.conn, "NOPRICE.US")
        svc = self.import_svc()
        holdings = svc.get_holdings()
        self.assertEqual(len(holdings), 1)
        self.assertIsNone(holdings[0].current_value)

    def test_holdings_unrealized_pl(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        holdings = svc.get_holdings()
        aapl = next(h for h in holdings if h.market_code == "AAPL.US" and h.layer.name == "CORE")
        self.assertIsNotNone(aapl.unrealized_pl)
        expected_pl = (8.0 * 200.0) - (8.0 * 150.0)
        self.assertAlmostEqual(aapl.unrealized_pl, expected_pl)

    def test_holdings_weight_pct_sums_to_100(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        holdings = svc.get_holdings()
        total = sum(h.weight_pct for h in holdings if h.current_value is not None)
        self.assertAlmostEqual(total, 100.0, places=4)

    def test_allocation_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.get_asset_allocation("layer"), [])

    def test_allocation_by_layer(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        alloc = svc.get_asset_allocation("layer")
        categories = {a.category for a in alloc}
        self.assertIn("core", categories)
        self.assertIn("satellite", categories)
        self.assertIn("reserve", categories)

    def test_allocation_by_asset_type(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        alloc = svc.get_asset_allocation("asset_type")
        categories = {a.category for a in alloc}
        self.assertIn("STOCK", categories)
        self.assertIn("ETF", categories)
        self.assertIn("CRYPTO", categories)

    def test_allocation_by_currency(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        alloc = svc.get_asset_allocation("currency")
        categories = {a.category for a in alloc}
        self.assertIn("USD", categories)
        self.assertIn("EUR", categories)

    def test_allocation_invalid_dimension(self):
        svc = self.import_svc()
        with self.assertRaises(svc.AnalyticsError):
            svc.get_asset_allocation("invalid")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

test_app = FastAPI()
from routes.analytics import router
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


class TestAnalyticsRoutes(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.patcher = patch("services.analytics_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_dashboard_empty(self):
        resp = client.get("/api/v1/analytics/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_portfolio_value"], 0.0)

    def test_dashboard_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_portfolio_value", data)
        self.assertIn("num_holdings", data)
        self.assertEqual(data["num_holdings"], 4)

    def test_holdings_empty(self):
        resp = client.get("/api/v1/analytics/holdings")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_holdings_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/holdings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 4)
        self.assertIn("portfolio_asset_id", data[0])
        self.assertIn("weight_pct", data[0])

    def test_allocation_default(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/allocation")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["dimension"], "layer")

    def test_allocation_by_asset_type(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/allocation?dimension=asset_type")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data[0]["dimension"], "asset_type")

    def test_allocation_by_currency(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/allocation?dimension=currency")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data[0]["dimension"], "currency")

    def test_allocation_invalid_dimension(self):
        resp = client.get("/api/v1/analytics/allocation?dimension=invalid")
        self.assertEqual(resp.status_code, 400)

    def test_allocation_empty(self):
        resp = client.get("/api/v1/analytics/allocation")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


if __name__ == "__main__":
    unittest.main()
