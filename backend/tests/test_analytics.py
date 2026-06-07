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
    asset_class: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO market_assets (market_code, ticker, asset_type, currency_code, name, asset_class) VALUES (?, ?, ?, ?, ?, ?)",
        (code, ticker, asset_type, currency_code, name or code, asset_class),
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
    seed_entity(conn, 1, "Main Broker")
    seed_market_asset(conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple Inc.", "VI")
    seed_market_asset(conn, "VWCE.MC", "VWCE", "ETF", "EUR", "FTSE All-World", "VI")
    seed_market_asset(conn, "BTC", "BTC", "CRYPTO", "USD", "Bitcoin", "Monetary")
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

    def test_holdings_raw_includes_asset_class(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_holdings_raw(self.conn)
        aapl = next(r for r in rows if r["market_code"] == "AAPL.US")
        self.assertEqual(aapl["asset_class"], "VI")
        btc = next(r for r in rows if r["market_code"] == "BTC")
        self.assertEqual(btc["asset_class"], "Monetary")

    def test_holdings_by_entity_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_holdings_by_entity_raw(self.conn), [])

    def test_holdings_by_entity_raw_with_data(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_holdings_by_entity_raw(self.conn)
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIn("entity_id", r)
            self.assertIn("asset_class", r)
            self.assertIn("current_value", r)

    def test_cash_by_entity_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_cash_by_entity_raw(self.conn), [])

    def test_cash_by_entity_raw_with_data(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn, 1, "Bank")
        seed_tx(self.conn, "MONEY_IN", 1, "USD", 10000.0)
        seed_tx(self.conn, "MONEY_OUT", 1, "USD", 3000.0)
        q = self.import_q()
        rows = q.get_cash_by_entity_raw(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cash_balance"], 7000.0)

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
        self.assertEqual(q.get_cash_flow_raw(self.conn, "month"), [])

    def test_cash_flow_basic(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow_raw(self.conn, "month")
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIn("period", r)
            self.assertIn("type", r)

    def test_cash_flow_with_date_filter(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow_raw(self.conn, "month", start="2025-06-01")
        self.assertEqual(rows, [])

    def test_cash_flow_group_by_year(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_cash_flow_raw(self.conn, "year")
        self.assertGreater(len(rows), 0)
        self.assertEqual(len(set(r["period"] for r in rows)), 1)

    def test_dividends_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_dividends_raw(self.conn), [])

    def test_dividends_basic(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        q = self.import_q()
        rows = q.get_dividends_raw(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_dividends"], 50.0)

    def test_dividends_with_date_filter(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        q = self.import_q()
        rows = q.get_dividends_raw(self.conn, end="2025-01-01")
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

    def test_buy_sell_transactions_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_buy_sell_transactions(self.conn), [])

    def test_buy_sell_transactions_basic(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        rows = q.get_buy_sell_transactions(self.conn)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["type"], "INVESTMENT_BUY")
        self.assertEqual(rows[1]["type"], "INVESTMENT_SELL")

    def test_net_positions_as_of(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        positions = q.get_net_positions_as_of(self.conn, "2025-06-01")
        self.assertGreater(len(positions), 0)

    def test_net_positions_as_of_before_all(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        positions = q.get_net_positions_as_of(self.conn, "2024-01-01")
        self.assertEqual(positions, [])

    def test_get_all_prices_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_all_prices(self.conn), [])

    def test_get_all_prices_basic(self):
        seed_full_scenario(self.conn)
        q = self.import_q()
        prices = q.get_all_prices(self.conn)
        self.assertEqual(len(prices), 3)


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

    def test_allocation_by_asset_class(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        alloc = svc.get_asset_allocation("asset_class")
        categories = {a.category for a in alloc}
        self.assertIn("VI", categories)
        self.assertIn("Monetary", categories)

    def test_allocation_by_entity(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        alloc = svc.get_asset_allocation("entity")
        self.assertGreater(len(alloc), 0)
        self.assertEqual(alloc[0].dimension, "entity")

    def test_allocation_invalid_dimension(self):
        svc = self.import_svc()
        with self.assertRaises(svc.AnalyticsError):
            svc.get_asset_allocation("invalid")

    def test_holdings_by_entity_empty(self):
        svc = self.import_svc()
        result = svc.get_holdings_by_entity()
        self.assertEqual(result, [])

    def test_holdings_by_entity_with_data(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        result = svc.get_holdings_by_entity()
        self.assertGreater(len(result), 0)
        for line in result:
            self.assertIn("entity_name", str(line))
            self.assertIsNotNone(line.current_value)

    def test_cash_flow_empty(self):
        svc = self.import_svc()
        result = svc.get_cash_flow()
        self.assertEqual(result.lines, [])
        self.assertEqual(result.total_in, 0.0)

    def test_cash_flow_basic(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        result = svc.get_cash_flow()
        self.assertGreater(len(result.lines), 0)
        self.assertGreater(result.total_in, 0)
        self.assertGreater(result.total_out, 0)

    def test_cash_flow_invalid_group_by(self):
        svc = self.import_svc()
        with self.assertRaises(svc.AnalyticsError):
            svc.get_cash_flow(group_by="invalid")

    def test_dividends_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.get_dividends(), [])

    def test_dividends_basic(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        svc = self.import_svc()
        result = svc.get_dividends()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].total_dividends, 50.0)

    def test_fees_taxes_empty(self):
        svc = self.import_svc()
        result = svc.get_fees_taxes()
        self.assertEqual(result.fees, [])
        self.assertEqual(result.taxes, [])
        self.assertEqual(result.total_fees, 0.0)

    def test_fees_taxes_with_data(self):
        seed_full_scenario(self.conn)
        tx_ids = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM transactions WHERE type='INVESTMENT_BUY'"
            ).fetchall()
        ]
        seed_fee(self.conn, tx_ids[0], "BROKER", "FIXED", 10.0)
        seed_tax(self.conn, tx_ids[0], "STAMP_DUTY", 5.0)
        svc = self.import_svc()
        result = svc.get_fees_taxes()
        self.assertGreater(len(result.fees), 0)
        self.assertGreater(len(result.taxes), 0)
        self.assertGreater(result.total_fees, 0)
        self.assertGreater(result.total_taxes, 0)

    def test_realized_gains_empty(self):
        svc = self.import_svc()
        self.assertEqual(svc.get_realized_gains(), [])

    def test_realized_gains_basic(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        gains = svc.get_realized_gains()
        self.assertEqual(len(gains), 1)
        self.assertEqual(gains[0].sell_quantity, 2.0)
        self.assertGreater(gains[0].realized_pl, 0)

    def test_realized_gains_with_multiple_buys(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 600.0, aid, 5, 120.0, "2025-02-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 880.0, aid, 8, 110.0, "2025-03-01T00:00:00Z")
        svc = self.import_svc()
        gains = svc.get_realized_gains()
        self.assertEqual(len(gains), 1)
        cost_basis = 8 * ((10 * 100 + 5 * 120) / 15)
        expected_pl = 880.0 - cost_basis
        self.assertAlmostEqual(gains[0].realized_pl, expected_pl, places=2)

    def test_performance_summary_empty(self):
        svc = self.import_svc()
        perf = svc.get_performance_summary()
        self.assertEqual(perf.total_portfolio_value, 0.0)
        self.assertEqual(perf.total_realized_pl, 0.0)

    def test_performance_summary_with_data(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        perf = svc.get_performance_summary()
        self.assertGreater(perf.total_portfolio_value, 0)
        self.assertGreater(perf.total_invested, 0)

    def test_historical_values_empty(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn)
        svc = self.import_svc()
        result = svc.get_historical_values("2025-01-01", "2025-03-01", "month")
        self.assertEqual(len(result), 3)
        for point in result:
            self.assertEqual(point.total_value, 0.0)

    def test_historical_values_with_data(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        result = svc.get_historical_values("2025-06-01", "2025-08-01", "month")
        self.assertGreater(len(result), 0)
        self.assertGreater(result[-1].total_value, 0)

    def test_historical_values_invalid_interval(self):
        svc = self.import_svc()
        with self.assertRaises(svc.AnalyticsError):
            svc.get_historical_values("2025-01-01", "2025-03-01", "invalid")


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

    def test_allocation_by_asset_class(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/allocation?dimension=asset_class")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["dimension"], "asset_class")

    def test_allocation_by_entity(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/allocation?dimension=entity")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["dimension"], "entity")

    def test_holdings_by_entity_empty(self):
        resp = client.get("/api/v1/analytics/holdings-by-entity")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_holdings_by_entity_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/holdings-by-entity")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        self.assertIn("entity_name", data[0])
        self.assertIn("asset_class", data[0])
        self.assertIn("current_value", data[0])

    def test_allocation_invalid_dimension(self):
        resp = client.get("/api/v1/analytics/allocation?dimension=invalid")
        self.assertEqual(resp.status_code, 400)

    def test_allocation_empty(self):
        resp = client.get("/api/v1/analytics/allocation")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_cash_flow_empty(self):
        resp = client.get("/api/v1/analytics/cash-flow")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["lines"], [])

    def test_cash_flow_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/cash-flow")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data["lines"]), 0)
        self.assertIn("total_in", data)

    def test_cash_flow_invalid_group_by(self):
        resp = client.get("/api/v1/analytics/cash-flow?group_by=invalid")
        self.assertEqual(resp.status_code, 400)

    def test_dividends_empty(self):
        resp = client.get("/api/v1/analytics/dividends")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_dividends_with_data(self):
        seed_full_scenario(self.conn)
        seed_dividend_tx(self.conn, 1, "USD", 50.0, 1)
        resp = client.get("/api/v1/analytics/dividends")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)

    def test_fees_taxes_empty(self):
        resp = client.get("/api/v1/analytics/fees-taxes")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["fees"], [])
        self.assertEqual(data["taxes"], [])

    def test_fees_taxes_with_data(self):
        seed_full_scenario(self.conn)
        tx_id = self.conn.execute(
            "SELECT id FROM transactions WHERE type='INVESTMENT_BUY' LIMIT 1"
        ).fetchone()[0]
        seed_fee(self.conn, tx_id, "BROKER", "FIXED", 10.0)
        seed_tax(self.conn, tx_id, "STAMP_DUTY", 5.0)
        resp = client.get("/api/v1/analytics/fees-taxes")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data["fees"]), 0)
        self.assertGreater(len(data["taxes"]), 0)

    def test_performance_empty(self):
        resp = client.get("/api/v1/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_portfolio_value"], 0.0)

    def test_performance_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_realized_pl", data)
        self.assertIn("total_unrealized_pl", data)

    def test_realized_gains_empty(self):
        resp = client.get("/api/v1/analytics/realized-gains")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_realized_gains_with_data(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/realized-gains")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)

    def test_historical_requires_dates(self):
        resp = client.get("/api/v1/analytics/historical")
        self.assertEqual(resp.status_code, 422)

    def test_historical_with_dates(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/historical?start_date=2025-01-01&end_date=2025-03-01")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)

    def test_historical_invalid_interval(self):
        resp = client.get("/api/v1/analytics/historical?start_date=2025-01-01&end_date=2025-03-01&interval=invalid")
        self.assertEqual(resp.status_code, 400)

    def test_cash_balances_empty(self):
        resp = client.get("/api/v1/analytics/cash-balances")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_cash_balances_with_snapshot(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 5000.0, '2025-01-01T00:00:00')"
        )
        resp = client.get("/api/v1/analytics/cash-balances")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["entity_id"], 1)
        self.assertEqual(data[0]["currency"], "USD")
        self.assertEqual(data[0]["balance"], 5000.0)

    def test_cash_balances_snapshot_and_transactions(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 1000.0, '2025-01-01T00:00:00')"
        )
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) VALUES ('2025-01-15T10:00:00', 'MONEY_IN', 1, 'USD', 500.0)"
        )
        resp = client.get("/api/v1/analytics/cash-balances")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["balance"], 1500.0)

    def test_cash_by_currency_history_empty(self):
        resp = client.get("/api/v1/analytics/cash-by-currency-history?start_date=2025-01-01&end_date=2025-03-01")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_cash_by_currency_history_with_snapshot(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 5000.0, '2025-01-01T00:00:00')"
        )
        resp = client.get("/api/v1/analytics/cash-by-currency-history?start_date=2025-01-01&end_date=2025-03-01")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        usd_entries = [d for d in data if d["currency"] == "USD"]
        self.assertGreater(len(usd_entries), 0)
        self.assertEqual(usd_entries[0]["balance"], 5000.0)

    def test_dashboard_cash_balance_includes_snapshots(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 10000.0, '2025-01-01T00:00:00')"
        )
        resp = client.get("/api/v1/analytics/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["cash_balance"], 10000.0)

    def test_historical_includes_cash(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 5000.0, '2025-01-01T00:00:00')"
        )
        seed_market_asset(self.conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple", "VI")
        seed_portfolio_asset(self.conn, "AAPL.US")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, portfolio_asset_id=1, quantity=10, unit_price=100.0)
        seed_price(self.conn, "AAPL.US", 150.0, "2025-02-01T00:00:00")
        resp = client.get("/api/v1/analytics/historical?start_date=2025-01-01&end_date=2025-03-01")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        feb_point = next((d for d in data if "2025-02" in d["date"]), None)
        self.assertIsNotNone(feb_point)
        self.assertGreater(feb_point["total_value"], 5000.0)

    def test_allocation_asset_class_includes_cash(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 10000.0, '2025-01-01T00:00:00')"
        )
        seed_market_asset(self.conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple", "VI")
        seed_portfolio_asset(self.conn, "AAPL.US")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 5000.0, portfolio_asset_id=1, quantity=50, unit_price=100.0)
        seed_price(self.conn, "AAPL.US", 100.0, "2025-02-01T00:00:00")
        resp = client.get("/api/v1/analytics/allocation?dimension=asset_class")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        cash_entry = next((d for d in data if d["category"] == "CASH"), None)
        self.assertIsNotNone(cash_entry)
        self.assertGreater(cash_entry["value_abs"], 0)

    def test_cash_by_entity_includes_dividends(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        seed_dividend_tx(self.conn, 1, "USD", 500.0)
        from db.analytics_queries import get_cash_by_entity_raw
        rows = get_cash_by_entity_raw(self.conn)
        broker_row = next((r for r in rows if r["entity_id"] == 1), None)
        self.assertIsNotNone(broker_row)
        self.assertGreater(broker_row["cash_balance"], 0)


if __name__ == "__main__":
    unittest.main()
