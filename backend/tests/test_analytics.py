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
        "INSERT INTO transactions (timestamp, type, income_category, entity_id, currency, total_value, portfolio_asset_id) VALUES (?, 'INCOME', 'dividends', ?, ?, ?, ?)",
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
    seed_tx(conn, "INCOME", 1, "USD", 10000.0)
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
        seed_tx(self.conn, "INCOME", 1, "USD", 10000.0)
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
        seed_tx(self.conn, "INCOME", 1, "USD", 10000.0)
        seed_tx(self.conn, "MONEY_OUT", 1, "USD", 3000.0)
        q = self.import_q()
        self.assertEqual(q.get_cash_balance(self.conn), 7000.0)

    def test_cash_balance_transfer_legs_directional(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn, 1, "Source Bank")
        seed_entity(self.conn, 2, "Dest Bank")
        seed_tx(self.conn, "INCOME", 1, "USD", 5000.0)
        seed_tx(self.conn, "TRANSFER_OUT", 1, "USD", 1000.0)
        seed_tx(self.conn, "TRANSFER_IN", 2, "USD", 1000.0)
        q = self.import_q()
        self.assertEqual(q.get_cash_balance(self.conn), 5000.0)
        rows = {r["entity_id"]: r for r in q.get_cash_by_entity_raw(self.conn)}
        self.assertEqual(rows[1]["cash_balance"], 4000.0)
        self.assertEqual(rows[2]["cash_balance"], 1000.0)

    def test_cash_flow_raw_groups_transfer_legs_separately(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn, 1, "Bank A")
        seed_entity(self.conn, 2, "Bank B")
        seed_tx(self.conn, "INCOME", 1, "USD", 1000.0)
        seed_tx(self.conn, "TRANSFER_OUT", 1, "USD", 500.0)
        seed_tx(self.conn, "TRANSFER_IN", 2, "USD", 500.0)
        q = self.import_q()
        rows = q.get_cash_flow_raw(self.conn, "month")
        self.assertEqual({r["type"] for r in rows}, {"INCOME", "TRANSFER_IN", "TRANSFER_OUT"})

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
        self.assertEqual(len({r["period"] for r in rows}), 1)

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
        tx_ids = [
            r["id"] for r in self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY'").fetchall()
        ]
        seed_fee(self.conn, tx_ids[0])
        q = self.import_q()
        rows = q.get_fees_raw(self.conn)
        self.assertEqual(len(rows), 1)

    def test_taxes_raw_empty(self):
        q = self.import_q()
        self.assertEqual(q.get_taxes_raw(self.conn), [])

    def test_taxes_raw_basic(self):
        seed_full_scenario(self.conn)
        tx_ids = [
            r["id"] for r in self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY'").fetchall()
        ]
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

    def test_buy_sell_transactions_includes_inactive_assets(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, is_active=0)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 1100.0, aid, 10, 110.0, "2025-03-01T00:00:00Z")
        q = self.import_q()
        rows = q.get_buy_sell_transactions(self.conn)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["type"] for r in rows}, {"INVESTMENT_BUY", "INVESTMENT_SELL"})

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
        self.patcher2 = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
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
        self.assertEqual(d.display_currency, "USD")

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

    def test_cash_flow_excludes_transfers(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn, 1, "Bank A")
        seed_entity(self.conn, 2, "Bank B")
        seed_tx(self.conn, "INCOME", 1, "USD", 1000.0)
        seed_tx(self.conn, "TRANSFER_OUT", 1, "USD", 500.0)
        seed_tx(self.conn, "TRANSFER_IN", 2, "USD", 500.0)
        svc = self.import_svc()
        result = svc.get_cash_flow()
        self.assertEqual(result.total_in, 1000.0)
        self.assertEqual(result.total_out, 0.0)

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
            r["id"] for r in self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY'").fetchall()
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
        cost_basis = 8 * 100.0  # FIFO consumes the earliest (10 @ 100) lot first
        expected_pl = 880.0 - cost_basis
        self.assertAlmostEqual(gains[0].cost_basis, cost_basis, places=2)
        self.assertAlmostEqual(gains[0].realized_pl, expected_pl, places=2)

    def test_realized_gains_inactive_asset(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, is_active=0)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 1100.0, aid, 10, 110.0, "2025-03-01T00:00:00Z")
        svc = self.import_svc()
        gains = svc.get_realized_gains()
        self.assertEqual(len(gains), 1)
        self.assertAlmostEqual(gains[0].cost_basis, 1000.0, places=2)
        self.assertAlmostEqual(gains[0].realized_pl, 100.0, places=2)

    def test_performance_summary_empty(self):
        svc = self.import_svc()
        perf = svc.get_performance_summary()
        self.assertEqual(perf.total_portfolio_value, 0.0)
        self.assertEqual(perf.total_realized_pl, 0.0)
        self.assertEqual(perf.realized_pl_pct, 0.0)

    def test_performance_summary_with_data(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        perf = svc.get_performance_summary()
        self.assertGreater(perf.total_portfolio_value, 0)
        self.assertGreater(perf.total_invested_now, 0)
        self.assertGreater(perf.total_invested_historic, 0)
        self.assertIsInstance(perf.unrealized_pl_pct, (int, float))
        self.assertIsInstance(perf.realized_pl_pct, (int, float))

    def test_performance_summary_realized_pl_pct_vs_sold_cost_basis(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 1100.0, aid, 10, 110.0, "2025-03-01T00:00:00Z")
        svc = self.import_svc()
        perf = svc.get_performance_summary("USD")
        # realized 100.0 over a sold cost basis of 1000.0
        self.assertAlmostEqual(perf.realized_pl_pct, 10.0, places=2)

    def test_performance_summary_realized_pl_pct_invariant_across_display_currency(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 1100.0, aid, 10, 110.0, "2025-03-01T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-03-01T00:00:00Z"),
        )
        svc = self.import_svc()
        usd = svc.get_performance_summary("USD")
        eur = svc.get_performance_summary("EUR")
        self.assertAlmostEqual(usd.realized_pl_pct, 10.0, places=2)
        self.assertAlmostEqual(eur.realized_pl_pct, usd.realized_pl_pct, places=2)

    def test_performance_summary_currency_conversion(self):
        seed_full_scenario(self.conn)
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-01T00:00:00Z"),
        )
        svc = self.import_svc()
        usd = svc.get_performance_summary("USD")
        eur = svc.get_performance_summary("EUR")
        self.assertEqual(eur.display_currency, "EUR")
        self.assertAlmostEqual(eur.total_portfolio_value, usd.total_portfolio_value * 0.5, places=1)
        self.assertAlmostEqual(eur.total_invested_historic, usd.total_invested_historic * 0.5, places=1)
        self.assertAlmostEqual(eur.total_realized_pl, usd.total_realized_pl * 0.5, places=1)
        self.assertAlmostEqual(eur.unrealized_pl_pct, usd.unrealized_pl_pct, places=2)
        self.assertAlmostEqual(eur.total_return_pct, usd.total_return_pct, places=2)

    def test_performance_summary_invested_historic_buy_date_conversion(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 100.0, None, None, None, "2025-01-15T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 200.0, None, None, None, "2025-03-15T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-15T00:00:00Z"),
        )
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.8, "2025-03-15T00:00:00Z"),
        )
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        self.assertAlmostEqual(perf.total_invested_historic, 100.0 * 0.5 + 200.0 * 0.8, places=4)

    def test_performance_summary_rate_fallback_closest_in_time(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 100.0, None, None, None, "2025-01-15T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-10T00:00:00Z"),
        )
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        self.assertTrue(any(f.reason == "closest-in-time" for f in perf.rate_fallbacks))
        self.assertAlmostEqual(perf.total_invested_historic, 100.0 * 0.5, places=4)

    def test_performance_summary_rate_fallback_no_rate(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 100.0, None, None, None, "2025-01-15T00:00:00Z")
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        self.assertTrue(any(f.reason == "no-rate" for f in perf.rate_fallbacks))
        self.assertAlmostEqual(perf.total_invested_historic, 100.0, places=4)

    def test_performance_summary_rule_key_from_locale(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        self.assertEqual(svc.get_performance_summary("USD", "es-ES").rule_key, "spain")
        self.assertEqual(svc.get_performance_summary("USD", "ja-JP").rule_key, "japan")
        self.assertEqual(svc.get_performance_summary("USD", "en-US").rule_key, "default")
        self.assertEqual(svc.get_performance_summary("USD").rule_key, "default")

    def test_performance_summary_per_sale_fiscal_rule(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 880.0, aid, 8, 110.0, "2025-03-01T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.9, "2025-01-01T00:00:00Z"),
        )
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.8, "2025-03-01T00:00:00Z"),
        )
        svc = self.import_svc()
        # Native gain = 880 - 800 = 80. Spain (locale) uses the sell-date rate.
        self.assertAlmostEqual(svc.get_performance_summary("EUR", "es-ES").total_realized_pl, 80 * 0.8, places=4)
        # A japan period covering the sell date converts each leg at its own date:
        # 880 * 0.8 (sell) - 800 * 0.9 (cost) = -16.
        self.conn.execute(
            "INSERT INTO fiscal_periods (rule_key, start_date, end_date) VALUES ('japan', '2025-01-01', '2025-12-31')"
        )
        self.conn.execute("UPDATE transactions SET fiscal_rule = 'japan' WHERE type = 'INVESTMENT_SELL'")
        self.assertAlmostEqual(svc.get_performance_summary("EUR", "es-ES").total_realized_pl, -16.0, places=4)
        # 'none' snapshots convert as the default (Spain copy).
        self.conn.execute("UPDATE transactions SET fiscal_rule = 'none' WHERE type = 'INVESTMENT_SELL'")
        self.assertAlmostEqual(svc.get_performance_summary("EUR", "es-ES").total_realized_pl, 80 * 0.8, places=4)

    def test_performance_summary_aggregates_fallbacks(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 100.0, None, None, None, "2025-01-15T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 200.0, None, None, None, "2025-01-15T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-10T00:00:00Z"),
        )
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        matches = [f for f in perf.rate_fallbacks if f.reason == "closest-in-time"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].count, 2)

    def _seed_income(self, category: str, amount: float, currency: str = "USD", ts: str = "2025-02-01T00:00:00Z"):
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, income_category) "
            "VALUES (?, 'INCOME', 1, ?, ?, ?)",
            (ts, currency, amount, category),
        )

    def test_performance_summary_dividends_and_interest(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        self._seed_income("dividends", 100.0)
        self._seed_income("dividends", 50.0)
        self._seed_income("interest", 25.0)
        self._seed_income("salary", 5000.0)
        svc = self.import_svc()
        perf = svc.get_performance_summary("USD")
        self.assertAlmostEqual(perf.total_dividends, 150.0, places=4)
        self.assertAlmostEqual(perf.total_interest, 25.0, places=4)

    def test_performance_summary_total_return_includes_dividends(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        # Buy 10 @100, sell all @110 → realized +100; no holdings left.
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 1100.0, aid, 10, 110.0, "2025-03-01T00:00:00Z")
        self._seed_income("dividends", 50.0)
        svc = self.import_svc()
        perf = svc.get_performance_summary("USD")
        self.assertAlmostEqual(perf.total_realized_pl, 100.0, places=4)
        self.assertAlmostEqual(perf.total_dividends, 50.0, places=4)
        self.assertAlmostEqual(perf.total_return, 150.0, places=4)
        self.assertAlmostEqual(perf.total_return_pct, 15.0, places=4)

    def test_performance_summary_total_return_excludes_unrealized(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        # Buy 10 @100, sell 5 @110 → realized +50; 5 shares remain at price 90
        # → unrealized −50, which must NOT enter Total Return.
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 550.0, aid, 5, 110.0, "2025-03-01T00:00:00Z")
        seed_price(self.conn, "AAPL.US", 90.0)
        self._seed_income("dividends", 20.0)
        svc = self.import_svc()
        perf = svc.get_performance_summary("USD")
        self.assertAlmostEqual(perf.total_realized_pl, 50.0, places=4)
        assert perf.total_unrealized_pl < 0
        self.assertAlmostEqual(perf.total_dividends, 20.0, places=4)
        self.assertAlmostEqual(perf.total_return, 70.0, places=4)

    def test_performance_summary_dividend_yield_pct_on_invested_historic(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        # Invested historic: 100 USD @0.5 (=50) + 200 EUR = 250 EUR basis.
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 100.0, None, None, None, "2025-01-15T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "EUR", 200.0, None, None, None, "2025-01-15T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-15T00:00:00Z"),
        )
        self._seed_income("dividends", 50.0, "EUR")
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        self.assertAlmostEqual(perf.total_dividends, 50.0, places=4)
        self.assertAlmostEqual(perf.total_invested_historic, 250.0, places=4)
        self.assertAlmostEqual(perf.dividend_yield_pct, 20.0, places=4)

    def test_performance_summary_dividends_converted_at_payment_date(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        self._seed_income("dividends", 100.0, "USD", "2025-01-01T00:00:00Z")
        self._seed_income("interest", 40.0, "USD", "2025-06-01T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-01T00:00:00Z"),
        )
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.9, "2025-06-01T00:00:00Z"),
        )
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        self.assertAlmostEqual(perf.total_dividends, 50.0, places=4)
        self.assertAlmostEqual(perf.total_interest, 36.0, places=4)

    def test_performance_summary_income_rate_fallback_scope(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        self._seed_income("dividends", 100.0, "USD", "2025-03-01T00:00:00Z")
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-02-20T00:00:00Z"),
        )
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        fb = [f for f in perf.rate_fallbacks if f.scope == "dividends" and f.reason == "closest-in-time"]
        self.assertEqual(len(fb), 1)
        self.assertAlmostEqual(perf.total_dividends, 50.0, places=4)

    def test_performance_summary_interest_fallback_scope(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        self._seed_income("interest", 10.0, "USD", "2025-03-01T00:00:00Z")
        svc = self.import_svc()
        perf = svc.get_performance_summary("EUR")
        fb = [f for f in perf.rate_fallbacks if f.scope == "interest" and f.reason == "no-rate"]
        self.assertEqual(len(fb), 1)
        self.assertAlmostEqual(perf.total_interest, 10.0, places=4)

    def test_performance_summary_no_income_defaults_zero(self):
        seed_full_scenario(self.conn)
        svc = self.import_svc()
        perf = svc.get_performance_summary("USD")
        self.assertEqual(perf.total_dividends, 0.0)
        self.assertEqual(perf.total_interest, 0.0)
        self.assertEqual(perf.dividend_yield_pct, 0.0)

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

    def test_fifo_cost_basis_basic(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 600.0, aid, 5, 120.0, "2025-02-01T00:00:00Z")
        svc = self.import_svc()
        fifo = svc._compute_fifo_cost_basis(self.conn)
        self.assertIn(aid, fifo)
        self.assertAlmostEqual(fifo[aid]["qty"], 15.0)
        self.assertAlmostEqual(fifo[aid]["cost"], 1600.0)

    def test_fifo_cost_basis_skips_null_quantity(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, None, 100.0, "2025-01-01T00:00:00Z")
        svc = self.import_svc()
        fifo = svc._compute_fifo_cost_basis(self.conn)
        self.assertNotIn(aid, fifo)

    def test_realized_gains_skips_null_quantity(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        aid = seed_portfolio_asset(self.conn, "AAPL.US", "core")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1000.0, aid, 5, 200.0, "2025-01-01T00:00:00Z")
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 500.0, aid, None, 250.0, "2025-02-01T00:00:00Z")
        svc = self.import_svc()
        gains = svc.get_realized_gains()
        self.assertEqual(len(gains), 0)

    def _seed_rate(self, code: str, base: str, rate: float):
        from datetime import datetime

        from db import queries

        queries.insert_rate(self.conn, code, base, rate, datetime(2025, 6, 2))

    def test_rate_metadata_stale_passthrough_false(self):
        self._seed_rate("USD", "EUR", 1.08)
        svc = self.import_svc()
        with patch("services.analytics_svc.is_stale_rate", return_value=False) as stale_mock:
            meta = svc._get_rate_metadata(["USD"], "EUR")
        self.assertIsNotNone(meta)
        self.assertFalse(meta.stale)
        self.assertAlmostEqual(meta.rates["USD"], 1.08)
        stale_mock.assert_called_once()

    def test_rate_metadata_stale_passthrough_true(self):
        self._seed_rate("USD", "EUR", 1.08)
        svc = self.import_svc()
        with patch("services.analytics_svc.is_stale_rate", return_value=True):
            meta = svc._get_rate_metadata(["USD"], "EUR")
        self.assertIsNotNone(meta)
        self.assertTrue(meta.stale)

    def test_rate_metadata_none_when_no_conversion_needed(self):
        svc = self.import_svc()
        self.assertIsNone(svc._get_rate_metadata(["EUR"], "EUR"))

    def test_rate_metadata_none_when_pair_missing(self):
        svc = self.import_svc()
        self.assertIsNone(svc._get_rate_metadata(["GBP"], "EUR"))


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

from routes.analytics import router  # noqa: E402

test_app = FastAPI()

test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


class TestAnalyticsRoutes(unittest.TestCase):
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
        tx_id = self.conn.execute("SELECT id FROM transactions WHERE type='INVESTMENT_BUY' LIMIT 1").fetchone()[0]
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

    def test_performance_with_display_currency(self):
        seed_full_scenario(self.conn)
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
            ("USD", "EUR", 0.5, "2025-01-01T00:00:00Z"),
        )
        resp = client.get("/api/v1/analytics/performance?display_currency=EUR")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["display_currency"], "EUR")
        self.assertGreater(data["total_portfolio_value"], 0)

    def test_performance_locale_sets_rule_key(self):
        seed_full_scenario(self.conn)
        resp = client.get("/api/v1/analytics/performance?locale=es-ES")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["rule_key"], "spain")
        self.assertIsInstance(data["rate_fallbacks"], list)

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
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) VALUES ('2025-01-15T10:00:00', 'INCOME', 1, 'USD', 500.0)"
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
        assert feb_point is not None
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
        assert cash_entry is not None
        self.assertGreater(cash_entry["value_abs"], 0)

    def test_dashboard_portfolio_value_includes_cash(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 10000.0, '2025-01-01T00:00:00')"
        )
        seed_market_asset(self.conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple", "VI")
        seed_portfolio_asset(self.conn, "AAPL.US")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 5000.0, portfolio_asset_id=1, quantity=50, unit_price=100.0)
        seed_price(self.conn, "AAPL.US", 100.0, "2025-02-01T00:00:00")
        resp = client.get("/api/v1/analytics/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Assets: 50 * 100 = 5000
        # Cash: 10000 (snapshot) - 5000 (INVESTMENT_BUY) = 5000
        # Total Portfolio Value: 5000 + 5000 = 10000
        self.assertEqual(data["total_portfolio_value"], 10000.0)
        self.assertEqual(data["cash_balance"], 5000.0)
        self.assertEqual(data["total_invested"], 5000.0)

    def test_historical_entity_includes_cash(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES (1, 'USD', 10000.0, '2025-01-01T00:00:00')"
        )
        seed_market_asset(self.conn, "AAPL.US", "AAPL", "STOCK", "USD", "Apple", "VI")
        seed_portfolio_asset(self.conn, "AAPL.US")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 5000.0, portfolio_asset_id=1, quantity=50, unit_price=100.0)
        seed_price(self.conn, "AAPL.US", 100.0, "2025-02-01T00:00:00")
        resp = client.get("/api/v1/analytics/historical?start_date=2025-01-01&end_date=2025-03-01&entity_id=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        # At Feb 2025: Assets = 50 * 100 = 5000, Cash = 10000 - 5000 = 5000, Total = 10000
        feb_point = next((d for d in data if "2025-02" in d["date"]), None)
        self.assertIsNotNone(feb_point)
        assert feb_point is not None
        self.assertEqual(feb_point["total_value"], 10000.0)

    def test_cash_by_entity_includes_dividends(self):
        seed_entity(self.conn, 1, "Broker1")
        seed_currency(self.conn, "USD")
        seed_dividend_tx(self.conn, 1, "USD", 500.0)
        from db.analytics_queries import get_cash_by_entity_raw

        rows = get_cash_by_entity_raw(self.conn)
        assert rows is not None
        broker_row = next((r for r in rows if r["entity_id"] == 1), None)
        self.assertIsNotNone(broker_row)
        assert broker_row is not None
        self.assertGreater(broker_row["cash_balance"], 0)


class TestHoldingsPriceMetadata(unittest.TestCase):
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

    def _holding(self, market_code):
        from services import analytics_svc

        holdings = analytics_svc.get_holdings()
        return next(h for h in holdings if h.market_code == market_code)

    def test_market_api_source_and_as_of(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn, "AAPL.US")
        aid = seed_portfolio_asset(self.conn, "AAPL.US")
        seed_price(self.conn, "AAPL.US", 200.0, timestamp="2025-06-01T12:00:00Z")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1500.0, aid, 10, 150.0)
        h = self._holding("AAPL.US")
        self.assertEqual(h.price_source, "market-api")
        self.assertEqual(h.price_as_of, "2025-06-01T12:00:00Z")

    def test_transaction_fallback_source_and_as_of(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn, "VWCE.MC")
        aid = seed_portfolio_asset(self.conn, "VWCE.MC")
        seed_tx(
            self.conn,
            "INVESTMENT_BUY",
            1,
            "USD",
            1000.0,
            aid,
            10,
            100.0,
            timestamp="2025-03-10T09:00:00Z",
        )
        h = self._holding("VWCE.MC")
        self.assertEqual(h.price_source, "transaction-fallback")
        self.assertEqual(h.price_as_of, "2025-03-10T09:00:00Z")
        self.assertIsNone(h.latest_price)

    def test_manual_source_and_as_of(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn, "AAPL.US")
        aid = seed_portfolio_asset(self.conn, "AAPL.US", tracking_mode="manual")
        self.conn.execute(
            "INSERT INTO manual_values (portfolio_asset_id, value, effective_date) VALUES (?, ?, ?)",
            (aid, 5000.0, "2025-05-01"),
        )
        h = self._holding("AAPL.US")
        self.assertEqual(h.price_source, "manual")
        self.assertEqual(h.price_as_of, "2025-05-01")
        self.assertEqual(h.current_value, 5000.0)

    def test_manual_without_value_is_none(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn, "AAPL.US")
        seed_portfolio_asset(self.conn, "AAPL.US", tracking_mode="manual")
        h = self._holding("AAPL.US")
        self.assertEqual(h.price_source, "none")
        self.assertIsNone(h.price_as_of)
        self.assertIsNone(h.current_value)

    def test_no_price_source_is_none(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn, "NOPRICE.US")
        seed_portfolio_asset(self.conn, "NOPRICE.US")
        h = self._holding("NOPRICE.US")
        self.assertEqual(h.price_source, "none")
        self.assertIsNone(h.price_as_of)
        self.assertIsNone(h.current_value)

    def test_price_without_transactions_is_market_api(self):
        seed_currency(self.conn, "USD")
        seed_market_asset(self.conn, "AAPL.US")
        seed_portfolio_asset(self.conn, "AAPL.US")
        seed_price(self.conn, "AAPL.US", 200.0, timestamp="2025-06-01T12:00:00Z")
        h = self._holding("AAPL.US")
        self.assertEqual(h.price_source, "market-api")
        self.assertEqual(h.price_as_of, "2025-06-01T12:00:00Z")
        self.assertIsNone(h.current_value)

    def test_valuation_unchanged(self):
        seed_currency(self.conn, "USD")
        seed_entity(self.conn)
        seed_market_asset(self.conn, "AAPL.US")
        aid = seed_portfolio_asset(self.conn, "AAPL.US")
        seed_tx(self.conn, "INVESTMENT_BUY", 1, "USD", 1500.0, aid, 10, 150.0)
        seed_tx(self.conn, "INVESTMENT_SELL", 1, "USD", 500.0, aid, 2, 250.0)
        seed_price(self.conn, "AAPL.US", 200.0, timestamp="2025-06-01T12:00:00Z")
        h = self._holding("AAPL.US")
        self.assertEqual(h.net_quantity, 8.0)
        self.assertEqual(h.current_value, 1600.0)
        self.assertEqual(h.latest_price, 200.0)


class TestProjectedIncomeDateTime(unittest.TestCase):
    """get_projected_income must not crash on naive vs aware datetime comparisons."""

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

    def test_naive_schedule_dates_dont_crash(self):
        from services.analytics_svc import get_projected_income

        seed_currency(self.conn, "EUR")
        seed_entity(self.conn, 1, "Employer")
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01", "2027-12-31", "MONTHLY", 1, "EUR", "INCOME", 3000.0),
        )

        result = get_projected_income()
        self.assertEqual(len(result.data), 16)
        self.assertEqual(result.data[0].total_value, 3000.0)

    def test_timezone_aware_schedule_dates_work(self):
        from services.analytics_svc import get_projected_income

        seed_currency(self.conn, "EUR")
        seed_entity(self.conn, 1, "Employer")
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01T00:00:00Z", "2027-12-31T00:00:00Z", "MONTHLY", 1, "EUR", "INCOME", 3000.0),
        )

        result = get_projected_income()
        self.assertEqual(len(result.data), 16)
        self.assertEqual(result.data[0].total_value, 3000.0)


class TestIncomeBySourceType(unittest.TestCase):
    """Income analytics must be grouped by transaction type so the chart can classify by category."""

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

    def _seed(self) -> None:
        seed_currency(self.conn, "EUR")
        for eid, name, etype in ((1, "Acme Corp", "EMPLOYER"), (2, "Local Bank", "BANK"), (3, "Broker", "BROKER")):
            self.conn.execute(
                "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
                (eid, name, etype),
            )
        txns = [
            ("2025-03-01T10:00:00Z", "INCOME", 1, 3000.0, None),
            ("2025-03-05T10:00:00Z", "INCOME", 2, 750.0, None),
            ("2025-03-10T10:00:00Z", "INCOME", 3, 124.5, "dividends"),
            ("2025-03-15T10:00:00Z", "INCOME", 2, 18.42, "interest"),
        ]
        for ts, t, eid, val, cat in txns:
            self.conn.execute(
                "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, income_category) VALUES (?, ?, ?, 'EUR', ?, ?)",
                (ts, t, eid, val, cat),
            )

    def _seed_schedules(self) -> None:
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01", "2026-12-31", "MONTHLY", 1, "EUR", "INCOME", 3000.0),
        )
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value, income_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Quarterly dividend", "2025-01-01", "2026-12-31", "QUARTERLY", 3, "EUR", "INCOME", 124.5, "dividends"),
        )

    def test_income_by_source_returns_type_per_row(self):
        from services.analytics_svc import get_income_by_source

        self._seed()
        result = get_income_by_source("month")
        lines = {(r.type, r.entity_name, r.total_value) for r in result.data}
        self.assertIn(("INCOME", "Acme Corp", 3000.0), lines)
        self.assertIn(("INCOME", "Local Bank", 750.0), lines)
        self.assertIn(("INCOME", "Broker", 124.5), lines)
        self.assertIn(("INCOME", "Local Bank", 18.42), lines)
        self.assertTrue(all(r.type == "INCOME" for r in result.data))

    def test_income_by_source_derives_category_fallback(self):
        from services.analytics_svc import get_income_by_source

        self._seed()
        result = get_income_by_source("month")
        categories = {(r.entity_name, r.income_category) for r in result.data}
        self.assertIn(("Acme Corp", "salary"), categories)
        self.assertIn(("Local Bank", "other"), categories)
        self.assertIn(("Broker", "dividends"), categories)
        self.assertIn(("Local Bank", "interest"), categories)

    def test_explicit_income_category_overrides_fallback(self):
        from services.analytics_svc import get_income_by_source

        seed_currency(self.conn, "EUR")
        self.conn.execute(
            "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
            (1, "Local Bank", "BANK"),
        )
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, income_category) "
            "VALUES (?, ?, ?, 'EUR', ?, ?)",
            ("2025-03-01T10:00:00Z", "INCOME", 1, 3000.0, "salary"),
        )
        result = get_income_by_source("month")
        self.assertEqual(len(result.data), 1)
        line = result.data[0]
        self.assertEqual(line.income_category, "salary")
        self.assertEqual(line.type, "INCOME")
        self.assertEqual(line.total_value, 3000.0)

    def test_projected_income_returns_type_per_row(self):
        from services.analytics_svc import get_projected_income

        self._seed()
        self._seed_schedules()
        result = get_projected_income()
        lines = {(r.type, r.entity_name, r.total_value) for r in result.data}
        self.assertIn(("INCOME", "Acme Corp", 3000.0), lines)
        self.assertIn(("INCOME", "Broker", 124.5), lines)

    def test_projected_income_category_from_schedule(self):
        from services.analytics_svc import get_projected_income

        seed_currency(self.conn, "EUR")
        self.conn.execute(
            "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
            (1, "Local Bank", "BANK"),
        )
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value, income_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01", "2026-12-31", "MONTHLY", 1, "EUR", "INCOME", 3000.0, "salary"),
        )
        result = get_projected_income()
        lines = {(r.type, r.income_category, r.entity_name, r.total_value) for r in result.data}
        self.assertIn(("INCOME", "salary", "Local Bank", 3000.0), lines)

    def test_projected_income_derives_employer_fallback(self):
        from services.analytics_svc import get_projected_income

        seed_currency(self.conn, "EUR")
        self.conn.execute(
            "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
            (1, "Acme Corp", "EMPLOYER"),
        )
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01", "2026-12-31", "MONTHLY", 1, "EUR", "INCOME", 3000.0),
        )
        result = get_projected_income()
        lines = {(r.type, r.income_category, r.entity_name, r.total_value) for r in result.data}
        self.assertIn(("INCOME", "salary", "Acme Corp", 3000.0), lines)
        self.assertTrue(all(r.income_category == "salary" for r in result.data))

    def test_projected_income_excludes_categories_without_schedules(self):
        """With no schedules at all, projected income must be empty."""
        from services.analytics_svc import get_projected_income

        self._seed()  # seeds transactions for salary, interest, dividends
        result = get_projected_income()
        self.assertEqual(len(result.data), 0)

    def test_projected_income_only_schedule_categories(self):
        """Projected income only returns categories present on schedules."""
        from services.analytics_svc import get_projected_income

        seed_currency(self.conn, "EUR")
        for eid, name, etype in ((1, "Acme", "EMPLOYER"), (2, "Broker", "BROKER")):
            self.conn.execute(
                "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, ?)",
                (eid, name, etype),
            )
        # Seed salary schedule only — no dividends, interest, or cashback schedule
        self.conn.execute(
            """INSERT INTO schedules
               (description, start_date, end_date, periodicity_type, entity_id, currency, type, total_value, income_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Salary", "2025-01-01", "2026-12-31", "MONTHLY", 1, "EUR", "INCOME", 3000.0, "salary"),
        )
        result = get_projected_income()
        categories = {r.income_category for r in result.data}
        self.assertEqual(categories, {"salary"})
        self.assertTrue(all(r.income_category != "dividends" for r in result.data))
        self.assertTrue(all(r.income_category != "interest" for r in result.data))
        self.assertTrue(all(r.income_category != "cashback" for r in result.data))


if __name__ == "__main__":
    unittest.main()
