"""Unit tests for the data-driven tax engine (§17.7-§17.12)."""

import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path

from services.tax_engine import (
    TaxBand,
    apply_progressive,
    compute_fiscal_year,
    get_base_categories,
    get_base_rates,
    get_confirmed_tax_map,
    get_tax_definitions,
    resolve_tax_base,
)

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_tax_base(
    conn,
    ruleset_key,
    computation,
    categories=("capital_gains", "dividends"),
    flat_rate=None,
    brackets=None,
    year_start=None,
):
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


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def item(tx_id, category, ts_str, taxable, native, fiscal_rule, currency="EUR"):
    return {
        "transaction_id": tx_id,
        "category": category,
        "timestamp": ts(ts_str),
        "taxable_amount": taxable,
        "native_amount": native,
        "fiscal_rule": fiscal_rule,
        "currency": currency,
    }


class TestResolveBase(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()

    def test_resolves_most_recent_year_start_le_asked(self):
        seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS, year_start=2023)
        seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS, year_start=2025)
        row = resolve_tax_base(self.conn, "spain", 2024)
        assert row is not None
        self.assertEqual(row["year_start"], 2023)

    def test_resolves_exact_year(self):
        seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS, year_start=2025)
        row = resolve_tax_base(self.conn, "spain", 2025)
        assert row is not None
        self.assertEqual(row["year_start"], 2025)

    def test_falls_back_to_null_default(self):
        seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS, year_start=2024)
        seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS, year_start=None)
        row = resolve_tax_base(self.conn, "spain", 2021)
        assert row is not None
        self.assertIsNone(row["year_start"])

    def test_returns_none_when_absent(self):
        self.assertIsNone(resolve_tax_base(self.conn, "spain", 2025))

    def test_other_ruleset_not_resolved(self):
        seed_tax_base(self.conn, "japan", "flat", flat_rate=0.20315)
        self.assertIsNone(resolve_tax_base(self.conn, "spain", 2025))

    def test_get_base_categories_and_rates(self):
        base_id = seed_tax_base(
            self.conn, "spain", "progressive", categories=("capital_gains",), brackets=SPAIN_BRACKETS
        )
        self.assertEqual(get_base_categories(self.conn, base_id), ["capital_gains"])
        rates = get_base_rates(self.conn, base_id)
        self.assertEqual([(r.from_amount, r.to_amount, r.rate) for r in rates], SPAIN_BRACKETS)


class TestApplyProgressive(unittest.TestCase):
    def test_full_bottom_bracket(self):
        self.assertEqual(apply_progressive(0, 280, [TaxBand(0, 6000, 0.19)]), 53.2)

    def test_crosses_two_brackets(self):
        bands = [TaxBand(0, 6000, 0.19), TaxBand(6000, 50000, 0.21)]
        self.assertEqual(apply_progressive(0, 10000, bands), 6000 * 0.19 + 4000 * 0.21)

    def test_middle_window_crosses_boundary(self):
        bands = [TaxBand(0, 6000, 0.19), TaxBand(6000, 50000, 0.21)]
        self.assertEqual(apply_progressive(4000, 8000, bands), 2000 * 0.19 + 2000 * 0.21)

    def test_open_top_bracket(self):
        bands = [TaxBand(0, 6000, 0.19), TaxBand(6000, 50000, 0.21), TaxBand(50000, None, 0.23)]
        total = apply_progressive(0, 60000, bands)
        self.assertAlmostEqual(total, 6000 * 0.19 + 44000 * 0.21 + 10000 * 0.23, places=4)

    def test_non_positive_or_no_bands_yields_zero(self):
        self.assertEqual(apply_progressive(10, 10, [TaxBand(0, 6000, 0.19)]), 0.0)
        self.assertEqual(apply_progressive(0, 100, []), 0.0)


def _convert_factory(rate=1.0):
    def convert(amount, currency, at):
        return amount * rate

    return convert


class TestComputeFiscalYear(unittest.TestCase):
    _AUTO = object()

    def setUp(self):
        self.conn = in_memory_db()

    def _fiscal(self, items, ruleset="spain", base=_AUTO, computation="progressive", flat_rate=None):
        if base is self._AUTO:
            base = seed_tax_base(
                self.conn,
                ruleset,
                computation,
                brackets=SPAIN_BRACKETS if computation == "progressive" else None,
                flat_rate=flat_rate,
            )
        base_row = (
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone())
            if isinstance(base, int)
            else base
        )
        return compute_fiscal_year(
            items,
            base_row,
            get_base_categories(self.conn, base) if isinstance(base, int) else [],
            get_base_rates(self.conn, base) if isinstance(base, int) else [],
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )

    def test_gains_only_progressive(self):
        items = [item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain")]
        result = self._fiscal(items)
        self.assertEqual(result.tax_owed, {"capital_gains": 15.2})
        self.assertEqual(result.combined_base, 80.0)
        self.assertEqual(result.total_tax_owed, 15.2)
        self.assertEqual(result.per_item[0].tax_owed, 15.2)

    def test_chronological_attribution_worked_example(self):
        # Sell 80 in June, dividend 200 in August: each taxed independently in
        # the bottom bracket (decision 10), not combined.
        items = [
            item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain"),
            item(2, "dividends", "2025-08-01", 200.0, 200.0, "spain"),
        ]
        result = self._fiscal(items)
        self.assertEqual(result.tax_owed, {"capital_gains": 15.2, "dividends": 38.0})
        self.assertEqual(result.total_tax_owed, 53.2)
        self.assertEqual(result.combined_base, 280.0)

    def test_chronological_order_affects_running_bracket(self):
        # Both dates fall before the first bracket boundary (280 < 6000), so
        # order does not change this outcome — assert the invariant below.
        items = [
            item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain"),
            item(2, "dividends", "2025-08-01", 200.0, 200.0, "spain"),
        ]
        result = self._fiscal(items)
        self.assertAlmostEqual(result.total_tax_owed, 280 * 0.19, places=4)

    def test_running_total_into_second_bracket(self):
        # First item fills 5800 of the 6000 bottom bracket; the next 400 spans
        # the boundary: 200 at 19%, 200 at 21%.
        items = [
            item(1, "capital_gains", "2025-01-01", 5800.0, 5800.0, "spain"),
            item(2, "dividends", "2025-06-15", 400.0, 400.0, "spain"),
        ]
        result = self._fiscal(items)
        expected = 5800 * 0.19 + 200 * 0.19 + 200 * 0.21
        self.assertAlmostEqual(result.total_tax_owed, expected, places=4)
        self.assertAlmostEqual(result.tax_owed["dividends"], 200 * 0.19 + 200 * 0.21, places=4)

    def test_flat_per_item(self):
        items = [
            item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "japan"),
            item(2, "dividends", "2025-08-01", 200.0, 200.0, "japan"),
        ]
        result = self._fiscal(items, ruleset="japan", computation="flat", flat_rate=0.20315)
        self.assertEqual(result.combined_base, None)
        self.assertAlmostEqual(result.tax_owed["capital_gains"], 80 * 0.20315, places=4)
        self.assertAlmostEqual(result.tax_owed["dividends"], 200 * 0.20315, places=4)
        self.assertAlmostEqual(result.total_tax_owed, 280 * 0.20315, places=4)
        self.assertEqual(result.withholding, 0.0)

    def test_no_base_yields_graceful_zeros(self):
        result = self._fiscal([item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain")], base=None)
        self.assertEqual(result.tax_owed, {})
        self.assertEqual(result.total_tax_owed, 0.0)
        self.assertIsNone(result.combined_base)
        self.assertEqual(result.per_item[0].tax_owed, 0.0)

    def test_item_outside_categories_excluded_from_base(self):
        items = [item(1, "interest", "2025-06-15", 50.0, 50.0, "spain")]
        result = self._fiscal(items)
        self.assertEqual(result.base, 0.0)
        self.assertEqual(result.tax_owed, {})
        self.assertEqual(result.total_tax_owed, 0.0)
        self.assertEqual(result.per_item[0].tax_owed, 0.0)

    def test_withholding_generic_definition(self):
        # Generic (ruleset_key NULL) definition carries the year-level
        # withholding source; 11.11 reduces total but not per-item core tax.
        gen_id = self.conn.execute("INSERT INTO tax_definitions (slug, name) VALUES ('generic', 'Generic')").lastrowid
        items = [item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain")]
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, 'EUR')",
            (1, gen_id, 11.11),
        )
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )
        self.assertAlmostEqual(result.total_tax, 15.2, places=4)
        self.assertAlmostEqual(result.withholding, 11.11, places=4)
        self.assertAlmostEqual(result.total_tax_owed, 4.09, places=4)
        self.assertEqual(result.per_item[0].tax_owed, 15.2)

    def test_withholding_capped_at_total_tax(self):
        gen_id = self.conn.execute("INSERT INTO tax_definitions (slug, name) VALUES ('generic', 'Generic')").lastrowid
        items = [item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain")]
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, 'EUR')",
            (1, gen_id, 999.0),
        )
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )
        self.assertEqual(result.total_tax_owed, 0.0)

    def test_ruleset_scoped_definition_not_withheld(self):
        # A ruleset-scoped definition is per-item tax, never year-level withholding.
        def_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name, ruleset_key, rate) VALUES ('spain_levy', 'Spain Levy', 'spain', 0.005)"
        ).lastrowid
        items = [item(1, "capital_gains", "2025-06-15", 80.0, 80.0, "spain")]
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, 'EUR')",
            (1, def_id, 0.4),
        )
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )
        self.assertEqual(result.withholding, 0.0)
        self.assertEqual(result.total_tax_owed, 15.2)

    def test_per_definition_taxes_resolution(self):
        def_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name, ruleset_key, rate) VALUES ('withholding_dividend', 'Dividend Withholding', 'spain', 0.15)"
        ).lastrowid
        items = [item(1, "dividends", "2025-08-01", 200.0, 200.0, "spain")]
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, 'EUR')",
            (1, def_id, 30.0),
        )
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )
        taxes = result.per_item[0].taxes
        self.assertEqual(len(taxes), 1)
        self.assertEqual(taxes[0].slug, "withholding_dividend")
        self.assertAlmostEqual(taxes[0].computed, 30.0, places=4)
        self.assertEqual(taxes[0].confirmed, 30.0)

    def test_confirmed_accumulates_per_category(self):
        # Confirmed amounts per definition accumulate into the per-category
        # confirmed dict (§17.9/decision 5), converted to display currency.
        gen_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name) VALUES ('foreign_withholding', 'Foreign Withholding')"
        ).lastrowid
        tobin_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name, ruleset_key, rate) VALUES ('tasa_tobin', 'Tasa Tobin', 'spain', 0.002)"
        ).lastrowid
        items = [
            item(1, "capital_gains", "2025-06-15", 80.0, 8000.0, "spain", currency="USD"),
            item(2, "dividends", "2025-08-01", 200.0, 200.0, "spain"),
        ]
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        self.conn.executemany(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, ?)",
            [
                (1, gen_id, 11.11, "USD"),
                (2, tobin_id, 0.4, "EUR"),
            ],
        )
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),  # rate 1.0
            "EUR",
        )
        self.assertEqual(result.confirmed, {"capital_gains": 11.11, "dividends": 0.4})
        self.assertAlmostEqual(result.total_confirmed, 11.51, places=4)
        # Naive line: computed 0 + confirmed 11.11. The auto-applying tasa_tobin
        # also attaches to the gains item (ruleset matches): computed 0.002 × 8000.
        gains = next(r for r in result.per_item if r.transaction_id == 1)
        fh = next(t for t in gains.taxes if t.slug == "foreign_withholding")
        self.assertEqual(fh.computed, 0.0)
        self.assertEqual(fh.confirmed, 11.11)
        tobin_gains = next(t for t in gains.taxes if t.slug == "tasa_tobin")
        self.assertAlmostEqual(tobin_gains.computed, 16.0, places=4)
        self.assertIsNone(tobin_gains.confirmed)
        # Auto-applying line on the dividend: computed 0.002 × 200 + confirmed 0.4.
        divs = next(r for r in result.per_item if r.transaction_id == 2)
        self.assertEqual(len(divs.taxes), 1)
        self.assertEqual(divs.taxes[0].slug, "tasa_tobin")
        self.assertAlmostEqual(divs.taxes[0].computed, 0.4, places=4)
        div_confirmed = divs.taxes[0].confirmed
        assert div_confirmed is not None
        self.assertAlmostEqual(div_confirmed, 0.4, places=4)

    def test_no_base_surfaces_confirmed_taxes(self):
        # §17.11/§17.12: definitions resolve independently of the base — a
        # confirmed row still surfaces (and accumulates) with no tax_bases row.
        gen_id = self.conn.execute(
            "INSERT INTO tax_definitions (slug, name) VALUES ('foreign_withholding', 'Foreign Withholding')"
        ).lastrowid
        items = [item(1, "dividends", "2025-08-01", 200.0, 200.0, "spain")]
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) VALUES (?, ?, ?, 'EUR')",
            (1, gen_id, 12.5),
        )
        result = self._fiscal(items, base=None)
        self.assertEqual(result.tax_owed, {})
        self.assertEqual(result.total_tax_owed, 0.0)
        self.assertIsNone(result.combined_base)
        self.assertEqual(result.confirmed, {"dividends": 12.5})
        self.assertAlmostEqual(result.total_confirmed, 12.5, places=4)
        self.assertEqual(result.per_item[0].tax_owed, 0.0)
        self.assertEqual(len(result.per_item[0].taxes), 1)
        self.assertEqual(result.per_item[0].taxes[0].confirmed, 12.5)
        self.assertEqual(result.per_item[0].taxes[0].computed, 0.0)

    def test_definition_requires_match_to_item_rule(self):
        # Definitions apply only to matching fiscal_rule; non-matching → skip.
        self.conn.execute(
            "INSERT INTO tax_definitions (slug, name, ruleset_key, rate) VALUES ('dividend_wh', 'Div WH', 'spain', 0.15)"
        )
        base = seed_tax_base(self.conn, "spain", "progressive", brackets=SPAIN_BRACKETS)
        items = [item(1, "dividends", "2025-08-01", 200.0, 200.0, "japan")]
        result = compute_fiscal_year(
            items,
            dict(self.conn.execute("SELECT * FROM tax_bases WHERE id = ?", (base,)).fetchone()),
            get_base_categories(self.conn, base),
            get_base_rates(self.conn, base),
            get_tax_definitions(self.conn),
            get_confirmed_tax_map(self.conn),
            _convert_factory(),
            "EUR",
        )
        self.assertEqual(result.per_item[0].taxes, [])

    def test_confirmed_map_profile_scoped(self):
        gen_id = self.conn.execute("INSERT INTO tax_definitions (slug, name) VALUES ('generic', 'Generic')").lastrowid
        assert gen_id is not None
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency, profile_id) VALUES (1, ?, 5.0, 'EUR', 3)",
            (gen_id,),
        )
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency, profile_id) VALUES (1, ?, 9.0, 'EUR', 4)",
            (gen_id,),
        )
        from unittest.mock import patch

        with patch("db.queries._pid", return_value=3):
            confirmed = get_confirmed_tax_map(self.conn)
        # profile_id 4 != active 3 → excluded; only the active profile's 5.0 row remains.
        self.assertEqual(sorted(r["tax_amount"] for r in [confirmed[(1, gen_id)]]), [5.0])


if __name__ == "__main__":
    unittest.main()
