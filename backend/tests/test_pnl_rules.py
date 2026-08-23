import sqlite3
import unittest
from datetime import datetime
from pathlib import Path

from services.pnl_rules import (
    _PREVIOUS_CLOSE_GRACE_DAYS,
    NativeSale,
    NoRateError,
    PnlLot,
    RateLookup,
    compute_fifo,
    convert_sale,
    rule_for_locale,
)

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def _row(
    tx_id: int,
    aid: int,
    type_: str,
    timestamp: str,
    quantity: float | None,
    unit_price: float | None,
    total_value: float | None,
    currency: str = "USD",
    payment_currency: str | None = None,
    fx_rate: float | None = None,
) -> dict:
    return {
        "transaction_id": tx_id,
        "portfolio_asset_id": aid,
        "market_code": "AAPL.US",
        "ticker": "AAPL",
        "name": "Apple",
        "type": type_,
        "timestamp": timestamp,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_value": total_value,
        "currency": currency,
        "payment_currency": payment_currency,
        "fx_rate": fx_rate,
    }


class FakeRateProvider:
    """Deterministic rate provider keyed by (code, base) → [(date, rate)].

    Mirrors production semantics: strict on-or-before resolution with the
    4-day previous-close grace (§16.4).
    """

    def __init__(self, rates: dict[tuple[str, str], list[tuple[str, float]]]) -> None:
        self.rates = rates
        self.latest_rates: dict[tuple[str, str], float] = {}
        for pair, series in rates.items():
            if series:
                self.latest_rates[pair] = series[-1][1]

    def historical(self, code: str, base_code: str, at: datetime) -> RateLookup:
        series = self.rates.get((code, base_code), [])
        target = at.date()
        prior = [e for e in series if datetime.fromisoformat(e[0]).date() <= target]
        if not prior:
            raise NoRateError(f"No rate data for ({code}, {base_code})")
        used_date_str, rate = prior[-1]
        used = datetime.fromisoformat(used_date_str)
        fallback = (target - used.date()).days > _PREVIOUS_CLOSE_GRACE_DAYS
        return RateLookup(rate=rate, timestamp=used, fallback=fallback)

    def latest(self, code: str, base_code: str) -> RateLookup:
        if (code, base_code) not in self.latest_rates:
            raise NoRateError(f"No rate data for ({code}, {base_code})")
        series = self.rates[(code, base_code)]
        used = datetime.fromisoformat(series[-1][0])
        return RateLookup(rate=self.latest_rates[(code, base_code)], timestamp=used, fallback=False)


def _sale(
    sell_total: float,
    lots: list[PnlLot],
    sell_date: str = "2025-03-01T10:00:00Z",
    currency: str = "USD",
    payment_currency: str | None = None,
    fx_rate: float | None = None,
) -> NativeSale:
    cost_basis = round(sum(lot.quantity * lot.unit_cost for lot in lots), 4)
    return NativeSale(
        transaction_id=1,
        portfolio_asset_id=1,
        market_code="AAPL.US",
        ticker="AAPL",
        name="Apple",
        sell_date=datetime.fromisoformat(sell_date.replace("Z", "+00:00")),
        sell_date_raw=sell_date,
        sell_quantity=sum(lot.quantity for lot in lots),
        sell_price=100.0,
        sell_total=sell_total,
        currency=currency,
        payment_currency=payment_currency,
        fx_rate=fx_rate,
        fiscal_rule=None,
        fiscal_exemption_id=None,
        lots=tuple(lots),
        cost_basis=cost_basis,
        realized_pl=round(sell_total - cost_basis, 4),
    )


class TestComputeFifo(unittest.TestCase):
    def test_consumes_lots_front_of_queue(self):
        rows = [
            _row(1, 1, "INVESTMENT_BUY", "2025-01-01T00:00:00Z", 10, 100.0, 1000.0),
            _row(2, 1, "INVESTMENT_BUY", "2025-02-01T00:00:00Z", 5, 120.0, 600.0),
            _row(3, 1, "INVESTMENT_SELL", "2025-03-01T00:00:00Z", 8, 110.0, 880.0),
        ]
        result = compute_fifo(rows)
        self.assertEqual(len(result.sales), 1)
        sale = result.sales[0]
        self.assertAlmostEqual(sale.cost_basis, 8 * 100.0)
        self.assertAlmostEqual(sale.realized_pl, 880.0 - 800.0)
        self.assertEqual(len(sale.lots), 1)
        self.assertEqual(sale.lots[0].quantity, 8.0)
        self.assertEqual(sale.lots[0].buy_date.date().isoformat(), "2025-01-01")

    def test_consumes_multiple_lots_and_retains_buy_dates(self):
        rows = [
            _row(1, 1, "INVESTMENT_BUY", "2025-01-01T00:00:00Z", 10, 100.0, 1000.0),
            _row(2, 1, "INVESTMENT_BUY", "2025-02-01T00:00:00Z", 5, 120.0, 600.0),
            _row(3, 1, "INVESTMENT_SELL", "2025-03-01T00:00:00Z", 12, 110.0, 1320.0),
        ]
        sale = compute_fifo(rows).sales[0]
        self.assertAlmostEqual(sale.cost_basis, 10 * 100.0 + 2 * 120.0)
        self.assertEqual([lot.buy_date.date().isoformat() for lot in sale.lots], ["2025-01-01", "2025-02-01"])

    def test_remaining_lots_carry_correct_cost(self):
        rows = [
            _row(1, 1, "INVESTMENT_BUY", "2025-01-01T00:00:00Z", 10, 100.0, 1000.0),
            _row(2, 1, "INVESTMENT_BUY", "2025-02-01T00:00:00Z", 5, 120.0, 600.0),
            _row(3, 1, "INVESTMENT_SELL", "2025-03-01T00:00:00Z", 8, 110.0, 880.0),
        ]
        result = compute_fifo(rows)
        remaining = result.remaining[1]
        qty = sum(lot.quantity for lot in remaining)
        cost = sum(lot.quantity * lot.unit_cost for lot in remaining)
        self.assertAlmostEqual(qty, 7.0)
        self.assertAlmostEqual(cost, 2 * 100.0 + 5 * 120.0)

    def test_sell_exceeding_available_consumes_what_exists(self):
        rows = [
            _row(1, 1, "INVESTMENT_BUY", "2025-01-01T00:00:00Z", 3, 100.0, 300.0),
            _row(2, 1, "INVESTMENT_SELL", "2025-02-01T00:00:00Z", 5, 110.0, 550.0),
        ]
        sale = compute_fifo(rows).sales[0]
        self.assertAlmostEqual(sale.cost_basis, 300.0)
        self.assertAlmostEqual(sale.realized_pl, 250.0)

    def test_skips_null_quantity(self):
        rows = [
            _row(1, 1, "INVESTMENT_BUY", "2025-01-01T00:00:00Z", None, 100.0, 1000.0),
            _row(2, 1, "INVESTMENT_SELL", "2025-02-01T00:00:00Z", 5, 110.0, 550.0),
        ]
        self.assertEqual(compute_fifo(rows).sales, [])

    def test_sell_with_no_prior_buy_is_ignored(self):
        rows = [_row(2, 1, "INVESTMENT_SELL", "2025-02-01T00:00:00Z", 5, 110.0, 550.0)]
        self.assertEqual(compute_fifo(rows).sales, [])


class TestRules(unittest.TestCase):
    def setUp(self):
        lots = [PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"))]
        self.sale = _sale(sell_total=880.0, lots=lots)  # native gain 80.0
        self.provider = FakeRateProvider(
            {
                ("USD", "EUR"): [("2025-01-01", 0.85), ("2025-03-01", 0.90), ("2025-04-01", 0.95)],
            }
        )

    def test_spain_uses_sale_day_rate(self):
        converted = convert_sale(self.sale, "spain", self.provider, "EUR")
        self.assertAlmostEqual(converted.value, 80.0 * 0.90)
        self.assertAlmostEqual(converted.cost_basis_display, 800.0 * 0.90)

    def test_default_matches_spain(self):
        spain = convert_sale(self.sale, "spain", self.provider, "EUR")
        default = convert_sale(self.sale, "default", self.provider, "EUR")
        self.assertAlmostEqual(default.value, spain.value)
        self.assertEqual(default.fallbacks, spain.fallbacks)

    def test_japan_converts_each_leg_at_its_own_date(self):
        lots = [
            PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00")),
            PnlLot(quantity=2, unit_cost=120.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00")),
        ]
        sale = _sale(sell_total=1100.0, lots=lots, sell_date="2025-03-01T10:00:00Z")
        # sell leg at 2025-03-01 rate (0.90); cost legs at buy date (2025-01-01, 0.85)
        expected = 1100.0 * 0.90 - (800.0 * 0.85 + 240.0 * 0.85)
        converted = convert_sale(sale, "japan", self.provider, "EUR")
        self.assertAlmostEqual(converted.value, expected)

    def test_japan_converts_cost_lots_at_different_buy_dates(self):
        provider = FakeRateProvider(
            {
                ("USD", "EUR"): [("2025-01-01", 0.80), ("2025-02-01", 0.85), ("2025-03-01", 0.90)],
            }
        )
        lots = [
            PnlLot(quantity=10, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00")),
            PnlLot(quantity=5, unit_cost=120.0, buy_date=datetime.fromisoformat("2025-02-01T00:00:00+00:00")),
        ]
        sale = _sale(sell_total=1800.0, lots=lots, sell_date="2025-03-01T10:00:00Z")
        expected = 1800.0 * 0.90 - (1000.0 * 0.80 + 600.0 * 0.85)
        converted = convert_sale(sale, "japan", provider, "EUR")
        self.assertAlmostEqual(converted.value, expected)
        self.assertAlmostEqual(converted.cost_basis_display, 1000.0 * 0.80 + 600.0 * 0.85)

    def test_latest_uses_latest_rate(self):
        converted = convert_sale(self.sale, "latest", self.provider, "EUR")
        self.assertAlmostEqual(converted.value, 80.0 * 0.95)
        self.assertAlmostEqual(converted.cost_basis_display, 800.0 * 0.95)

    def test_same_currency_needs_no_conversion(self):
        converted = convert_sale(self.sale, "spain", self.provider, "USD")
        self.assertAlmostEqual(converted.value, 80.0)
        self.assertAlmostEqual(converted.cost_basis_display, 800.0)

    def test_proceeds_currency_converts_from_payment_currency(self):
        provider = FakeRateProvider(
            {
                ("JPY", "EUR"): [("2025-03-01", 0.006)],
                ("USD", "EUR"): [("2025-03-01", 0.90)],
            }
        )
        sale = _sale(
            sell_total=1000.0,
            lots=[PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"))],
            payment_currency="JPY",
            fx_rate=150.0,
        )
        # proceeds = 1000 * 150 JPY = 150000 JPY → * 0.006 EUR; cost = 800 * 0.90 EUR
        expected = 150000.0 * 0.006 - 800.0 * 0.90
        converted = convert_sale(sale, "spain", provider, "EUR")
        self.assertAlmostEqual(converted.value, expected)

    def test_no_rate_uses_unconverted_and_flags(self):
        sale = _sale(
            sell_total=880.0,
            lots=[PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"))],
            currency="GBP",
        )
        provider = FakeRateProvider({})
        converted = convert_sale(sale, "spain", provider, "EUR")
        self.assertAlmostEqual(converted.value, 80.0)
        self.assertTrue(any(f.reason == "no-rate" for f in converted.fallbacks))

    def test_closest_in_time_fallback_flag(self):
        # Rate exists before the sale but beyond the previous-close grace
        # window (9 days) — conversion proceeds, fallback is reported.
        provider = FakeRateProvider({("USD", "EUR"): [("2025-02-20", 0.90)]})
        sale = _sale(
            sell_total=880.0,
            lots=[PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"))],
            sell_date="2025-03-01T10:00:00Z",
        )
        converted = convert_sale(sale, "spain", provider, "EUR")
        self.assertAlmostEqual(converted.value, 80.0 * 0.90)
        self.assertTrue(any(f.reason == "closest-in-time" for f in converted.fallbacks))

    def test_no_rate_before_sell_date_is_not_converted(self):
        # Only a later rate exists: strict on-or-before means NO lookahead.
        provider = FakeRateProvider({("USD", "EUR"): [("2025-03-10", 0.90)]})
        sale = _sale(
            sell_total=880.0,
            lots=[PnlLot(quantity=8, unit_cost=100.0, buy_date=datetime.fromisoformat("2025-01-01T00:00:00+00:00"))],
            sell_date="2025-03-01T10:00:00Z",
        )
        converted = convert_sale(sale, "spain", provider, "EUR")
        self.assertAlmostEqual(converted.value, 80.0)
        self.assertTrue(any(f.reason == "no-rate" for f in converted.fallbacks))


class TestRuleForLocale(unittest.TestCase):
    def test_spanish_locale(self):
        self.assertEqual(rule_for_locale("es-ES"), "spain")
        self.assertEqual(rule_for_locale("es"), "spain")

    def test_japanese_locale(self):
        self.assertEqual(rule_for_locale("ja-JP"), "japan")
        self.assertEqual(rule_for_locale("ja"), "japan")

    def test_unknown_and_empty_locale(self):
        self.assertEqual(rule_for_locale("en-US"), "default")
        self.assertEqual(rule_for_locale("de-DE"), "default")
        self.assertEqual(rule_for_locale(""), "default")


class TestPreviousCloseGrace(unittest.TestCase):
    """CurrencyServiceRateProvider grace semantics against a real DB (§16.4)."""

    def setUp(self):
        from unittest.mock import patch

        import db.queries as queries

        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.queries = queries
        # get_rate resolves pairs through currency_svc's own get_db().
        self.patcher = patch("services.currency_svc.get_db", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def _seed(self, rows):
        for code, base, rate, ts in rows:
            self.conn.execute(
                "INSERT INTO currencies VALUES (?, ?, ?, ?)",
                (code, base, rate, ts),
            )

    def test_weekend_resolves_silently_within_grace(self):
        from services.pnl_rules import CurrencyServiceRateProvider

        # Fri 19th + Mon 22nd stored (provider never serves the weekend).
        self._seed(
            [
                ("USD", "EUR", 1.05, "2025-09-19T00:00:00"),
                ("USD", "EUR", 1.06, "2025-09-22T00:00:00"),
            ]
        )
        provider = CurrencyServiceRateProvider()

        sat = provider.historical("USD", "EUR", datetime.fromisoformat("2025-09-20T12:00:00"))
        self.assertEqual(sat.rate, 1.05)
        self.assertFalse(sat.fallback)

        sun = provider.historical("USD", "EUR", datetime.fromisoformat("2025-09-21T12:00:00"))
        self.assertEqual(sun.rate, 1.05)
        self.assertFalse(sun.fallback)

        mon = provider.historical("USD", "EUR", datetime.fromisoformat("2025-09-22T10:00:00"))
        self.assertEqual(mon.rate, 1.06)
        self.assertFalse(mon.fallback)

    def test_stale_rate_beyond_grace_is_flagged(self):
        from services.pnl_rules import CurrencyServiceRateProvider

        self._seed([("USD", "EUR", 1.05, f"2025-09-{19 - _PREVIOUS_CLOSE_GRACE_DAYS - 1}T00:00:00")])
        provider = CurrencyServiceRateProvider()
        lookup = provider.historical("USD", "EUR", datetime.fromisoformat("2025-09-19T12:00:00"))
        self.assertEqual(lookup.rate, 1.05)
        self.assertTrue(lookup.fallback)

    def test_no_rate_on_or_before_raises(self):
        from services.pnl_rules import CurrencyServiceRateProvider

        self._seed([("USD", "EUR", 1.06, "2025-09-22T00:00:00")])
        provider = CurrencyServiceRateProvider()
        with self.assertRaises(NoRateError):
            provider.historical("USD", "EUR", datetime.fromisoformat("2025-09-20T12:00:00"))


if __name__ == "__main__":
    unittest.main()
