"""Tests for get_taxable_pnl_extended (§17.9, §17.10, §17.11)."""

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from db import queries

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


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


def seed_tax_base(
    conn,
    ruleset_key,
    computation,
    categories=("capital_gains", "dividends"),
    flat_rate=None,
    brackets=None,
    year_start=None,
):
    """Insert a tax_bases row + its categories and (progressive) brackets."""
    cur = conn.execute(
        "INSERT INTO tax_bases (ruleset_key, name, computation, flat_rate, year_start) VALUES (?, ?, ?, ?, ?)",
        (ruleset_key, ruleset_key, computation, flat_rate, year_start),
    )
    base_id = cur.lastrowid
    for cat in categories:
        conn.execute("INSERT INTO tax_base_categories (tax_base_id, category) VALUES (?, ?)", (base_id, cat))
    for from_amount, to_amount, rate in brackets or []:
        conn.execute(
            "INSERT INTO tax_base_rates (tax_base_id, from_amount, to_amount, rate) VALUES (?, ?, ?, ?)",
            (base_id, from_amount, to_amount, rate),
        )
    return base_id


SPAIN_BRACKETS = [(0, 6000, 0.19), (6000, 50000, 0.21), (50000, None, 0.23)]


def seed_spain(conn):
    return seed_tax_base(conn, "spain", "progressive", brackets=SPAIN_BRACKETS)


def seed_japan(conn):
    return seed_tax_base(conn, "japan", "flat", flat_rate=0.20315)


class TestTaxablePnlExtended(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
        self.conn.commit()
        # Seed Spain progressive base (§17.8)
        seed_spain(self.conn)
        self.conn.commit()
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

    def _seed_sell_scenario(self, rule=None, sell_total=880.0, sell_ts="2025-06-15T00:00:00Z"):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn, 1)
        seed_buy(self.conn, 1, "USD", 1000.0, 1, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_sell(self.conn, 1, "USD", sell_total, 1, 8, 110.0, sell_ts, fiscal_rule=rule)

    def test_basic_extended_shape(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES")
        self.assertEqual(result.ruleset, "spain")
        self.assertEqual(result.display_currency, "EUR")
        self.assertIsInstance(result.fiscal_years, list)
        self.assertEqual(len(result.fiscal_years), 1)
        year = result.fiscal_years[0]
        self.assertIsInstance(year.tax_owed, dict)
        self.assertIsInstance(year.items, list)
        self.assertEqual(len(year.items), 1)
        self.assertIn("capital_gains", year.tax_owed)
        self.assertIsInstance(result.total_tax_owed, float)

    def test_tax_owed_per_category_spain(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z")
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-08-01T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES", "spain")
        year = result.fiscal_years[0]
        # Spain: gains 80 + dividends 200 = 280 combined, progressive 19% on first 6000
        self.assertIn("capital_gains", year.tax_owed)
        self.assertIn("dividends", year.tax_owed)
        self.assertAlmostEqual(year.tax_owed["capital_gains"] + year.tax_owed["dividends"], 280 * 0.19, places=2)

    def test_japan_flat_per_category(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        # Seed Japan flat tax base
        seed_japan(self.conn)
        self.conn.commit()
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "", "japan")
        year = result.fiscal_years[0]
        # Japan: flat 20.315% per category
        self.assertIn("capital_gains", year.tax_owed)
        self.assertAlmostEqual(year.tax_owed["capital_gains"], 80 * 0.20315, places=2)

    def test_items_detail_correct(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES")
        item = result.fiscal_years[0].items[0]
        self.assertEqual(item.category, "capital_gains")
        self.assertEqual(item.currency, "USD")
        self.assertIsNotNone(item.date)
        self.assertIsNotNone(item.display_amount)
        self.assertIsNotNone(item.native_amount)
        # §17.12 per-definition breakdown present (no definitions seeded → empty).
        self.assertIsInstance(item.taxes, list)

    def test_zero_data(self):
        seed_currency(self.conn, "USD")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("USD", "es-ES")
        self.assertEqual(len(result.fiscal_years), 0)
        self.assertEqual(result.total_taxable, 0.0)
        # No tax_bases row configured → null, not 0.0.
        self.assertIsNone(result.total_tax_owed)
        # No transaction_taxes rows anywhere → null confirmed total.
        self.assertIsNone(result.total_confirmed)

    def test_default_ruleset_from_profile(self):
        self.conn.execute("UPDATE profiles SET default_fiscal_rule = 'japan' WHERE id = 1")
        self.conn.commit()
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("USD", "es-ES")
        self.assertEqual(result.default_ruleset, "japan")

    def test_default_ruleset_null_fallback(self):
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("USD", "es-ES")
        self.assertIsNone(result.default_ruleset)

    def test_exemption_reduces_tax_owed(self):
        eid = queries.create_fiscal_exemption(self.conn, "ISA", exemption_rate=50)
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        # Re-seed sell with exemption
        self.conn.execute("DELETE FROM transactions WHERE type = 'INVESTMENT_SELL'")
        seed_sell(self.conn, 1, "USD", 880.0, 1, 8, 110.0, "2025-06-15T00:00:00Z", exemption_id=eid)
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES")
        year = result.fiscal_years[0]
        # 50% exemption on 80 gain → 40 taxable at 19% = 7.6
        self.assertLess(year.tax_owed["capital_gains"], 80 * 0.19)

    def test_confirmed_tax_funds_yearly_withholding(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        active_profile, other_profile = 7, 9
        # Assign the seeded buy/sell to the active profile so item queries pick them up.
        self.conn.execute("UPDATE transactions SET profile_id = ?", (active_profile,))
        sell_id = self.conn.execute(
            "SELECT id FROM transactions WHERE type = 'INVESTMENT_SELL' ORDER BY id LIMIT 1"
        ).fetchone()[0]
        # Generic (ruleset_key NULL) definition that the confirmed WITHHOLDING funds.
        generic_def_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name) VALUES ('generic_withholding', 'Generic Withholding')"
        ).lastrowid
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_rate, tax_amount, currency, profile_id) VALUES (?, ?, NULL, ?, 'EUR', ?)",
            (sell_id, generic_def_id, 11.11, active_profile),
        )
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_rate, tax_amount, currency, profile_id) VALUES (?, ?, NULL, ?, 'EUR', ?)",
            (sell_id, generic_def_id, 99.99, other_profile),
        )
        self.conn.commit()
        # Plain in-memory conn can't carry profile_id; simulate the scoped value.
        with patch("db.queries._pid", return_value=active_profile):
            svc = self.import_svc()
            result = svc.get_taxable_pnl_extended("EUR", "es-ES")
            year = result.fiscal_years[0]
            # Gains-only: 0.19 × 80. The active profile's 11.11 EUR is withheld,
            # the other profile's 99.99 is excluded by profile scope.
            self.assertAlmostEqual(year.tax_owed["capital_gains"], 15.2, places=2)
            self.assertAlmostEqual(result.total_tax_owed, 15.2 - 11.11, places=2)
            # Decision 5, item 6: per-year post-withholding total (§17.9).
            self.assertAlmostEqual(year.total_tax_owed, 15.2 - 11.11, places=2)
            # Per-item surface: the attributed core tax (§17.12).
            item = year.items[0]
            self.assertAlmostEqual(item.tax_owed, 15.2, places=2)
            # §17.11/§17.12: the generic definition resolves its own line —
            # computed 0 (naive), confirmed from the active profile's row.
            self.assertEqual(len(item.taxes), 1)
            tax_line = item.taxes[0]
            self.assertEqual(tax_line.tax_definition_id, generic_def_id)
            self.assertEqual(tax_line.slug, "generic_withholding")
            self.assertEqual(tax_line.computed, 0.0)
            self.assertAlmostEqual(tax_line.confirmed, 11.11, places=2)
            # Decision 5, item 6: per-category confirmed + totals in display currency.
            self.assertEqual(year.confirmed, {"capital_gains": 11.11})
            self.assertAlmostEqual(year.total_confirmed, 11.11, places=2)
            self.assertAlmostEqual(result.total_confirmed, 11.11, places=2)
            # Summary total mirrors total_tax_owed's nullability — confirmed exists.
            self.assertIsNotNone(result.total_confirmed)

    def test_no_base_year_still_surfaces_confirmed(self):
        # §17.11/§17.12 + decision 5: with no japan tax_bases row, item.tax_owed
        # and total_tax_owed stay null, and total_confirmed is None at summary —
        # but the confirmed per-definition row is still surfaced on the item.
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-08-01T00:00:00Z")
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z")
        div_id = self.conn.execute("SELECT id FROM transactions WHERE type = 'INCOME'").fetchone()[0]
        def_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name, ruleset_key) VALUES ('foreign_withholding', 'Foreign Withholding', 'japan')"
        ).lastrowid
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, 12.5, 'EUR')",
            (div_id, def_id),
        )
        self.conn.commit()
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "", "japan")
        year = result.fiscal_years[0]
        self.assertEqual(year.tax_owed, {})
        # No base for japan → per-year total_tax_owed is null (no rates configured).
        self.assertIsNone(year.total_tax_owed)
        self.assertEqual(year.confirmed, {"dividends": 12.5})
        self.assertAlmostEqual(year.total_confirmed, 12.5, places=2)
        item = year.items[0]
        self.assertIsNone(item.tax_owed)
        self.assertEqual(len(item.taxes), 1)
        self.assertEqual(item.taxes[0].confirmed, 12.5)
        self.assertEqual(item.taxes[0].computed, 0.0)
        self.assertIsNone(result.total_tax_owed)
        self.assertAlmostEqual(result.total_confirmed, 12.5, places=2)

    def test_items_sorted_by_date(self):
        seed_currency(self.conn, "USD")
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-01-01T00:00:00Z")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn, 1)
        seed_buy(self.conn, 1, "USD", 1000.0, 1, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_sell(self.conn, 1, "USD", 600.0, 1, 5, 120.0, "2025-06-01T00:00:00Z")
        seed_sell(self.conn, 1, "USD", 700.0, 1, 5, 140.0, "2025-03-01T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES")
        items = result.fiscal_years[0].items
        dates = [i.date for i in items]
        self.assertEqual(dates, sorted(dates))

    def test_display_amount_plain_fx_vs_taxable_rule_japan(self):
        # The Japan per-lot rule makes taxable differ from the plain-FX display
        # amount: proceeds convert at the sell date while lot costs sit at their
        # buy-date rates.
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_market_asset(self.conn)
        seed_portfolio_asset(self.conn, 1)
        seed_buy(self.conn, 1, "USD", 1000.0, 1, 10, 100.0, "2025-01-01T00:00:00Z")
        seed_sell(self.conn, 1, "USD", 880.0, 1, 8, 110.0, "2025-06-15T00:00:00Z", fiscal_rule="japan")
        seed_rate(self.conn, "USD", "EUR", 0.9, "2025-01-01T00:00:00Z")
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "", "japan")
        item = result.fiscal_years[0].items[0]
        self.assertAlmostEqual(item.native_amount, 80.0, places=4)
        # Plain FX of the native gain at the sell-date rate (1.0).
        self.assertAlmostEqual(item.display_amount, 80.0, places=4)
        # Japan rule: proceeds 880×1.0 − cost 800×0.9 = 160.
        self.assertAlmostEqual(item.taxable_amount, 160.0, places=4)

    def test_tax_policy_and_display_with_exemption(self):
        eid = queries.create_fiscal_exemption(self.conn, "NISA", exemption_rate=50)
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        # Re-seed sell with exemption
        self.conn.execute("DELETE FROM transactions WHERE type = 'INVESTMENT_SELL'")
        seed_sell(self.conn, 1, "USD", 880.0, 1, 8, 110.0, "2025-06-15T00:00:00Z", exemption_id=eid)
        svc = self.import_svc()
        result = svc.get_taxable_pnl_extended("EUR", "es-ES")
        item = result.fiscal_years[0].items[0]
        self.assertEqual(item.tax_policy, "NISA")
        # Display amount is the plain conversion (exemption not applied).
        self.assertAlmostEqual(item.display_amount, 80.0, places=4)
        # Taxable amount is the post-exemption base (50% of 80).
        self.assertAlmostEqual(item.taxable_amount, 40.0, places=4)

    def test_fully_exempt_row_zero_taxable_keeps_display(self):
        eid = queries.create_fiscal_exemption(self.conn, "NISA", exemption_rate=100)
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        self.conn.execute("DELETE FROM transactions WHERE type = 'INVESTMENT_SELL'")
        seed_sell(self.conn, 1, "USD", 880.0, 1, 8, 110.0, "2025-06-15T00:00:00Z", exemption_id=eid)
        svc = self.import_svc()
        item = svc.get_taxable_pnl_extended("EUR", "es-ES").fiscal_years[0].items[0]
        self.assertAlmostEqual(item.taxable_amount, 0.0, places=4)
        self.assertAlmostEqual(item.display_amount, 80.0, places=4)
        self.assertEqual(item.tax_policy, "NISA")

    def test_tax_policy_none_without_exemption(self):
        self._seed_sell_scenario()
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-06-15T00:00:00Z")
        svc = self.import_svc()
        item = svc.get_taxable_pnl_extended("EUR", "es-ES").fiscal_years[0].items[0]
        self.assertIsNone(item.tax_policy)
        self.assertAlmostEqual(item.display_amount, 80.0, places=4)
        self.assertAlmostEqual(item.taxable_amount, 80.0, places=4)

    def test_dividend_fiscal_rule_resolved_per_date(self):
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-08-01T00:00:00Z")
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z")
        svc = self.import_svc()
        # No fiscal period → the dividend falls back to the resolved ruleset.
        item = svc.get_taxable_pnl_extended("EUR", "es-ES").fiscal_years[0].items[0]
        self.assertEqual(item.category, "dividends")
        self.assertEqual(item.fiscal_rule, "spain")
        # A japan period covering the payment date overrides the fallback.
        queries.create_fiscal_period(self.conn, "japan", "2025-01-01", "2025-12-31")
        item = svc.get_taxable_pnl_extended("EUR", "es-ES").fiscal_years[0].items[0]
        self.assertEqual(item.fiscal_rule, "japan")

    def test_dividend_exemption_tax_policy(self):
        eid = queries.create_fiscal_exemption(self.conn, "US Dividend Treaty", exemption_rate=50)
        seed_currency(self.conn, "USD")
        seed_currency(self.conn, "EUR")
        seed_entity(self.conn)
        seed_rate(self.conn, "USD", "EUR", 1.0, "2025-08-01T00:00:00Z")
        seed_dividend(self.conn, 1, "USD", 200.0, "2025-08-01T00:00:00Z", "2025-08-01T00:00:00Z", exemption_id=eid)
        svc = self.import_svc()
        item = svc.get_taxable_pnl_extended("EUR", "es-ES").fiscal_years[0].items[0]
        self.assertEqual(item.tax_policy, "US Dividend Treaty")
        self.assertAlmostEqual(item.display_amount, 200.0, places=4)
        self.assertAlmostEqual(item.taxable_amount, 100.0, places=4)


class TestTaxablePnlExtendedRoute(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
        self.conn.commit()
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
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from routes.analytics import router

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1")
        c = TestClient(test_app)
        resp = c.get("/api/v1/analytics/taxable-pnl-extended?display_currency=EUR&locale=es-ES")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("ruleset", data)
        self.assertIn("fiscal_years", data)
        self.assertIn("total_taxable", data)
        self.assertIn("total_tax_owed", data)
        self.assertIn("total_confirmed", data)
        self.assertIn("default_ruleset", data)


if __name__ == "__main__":
    unittest.main()
