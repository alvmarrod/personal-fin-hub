"""Tests for the TaxModel abstraction (§17.7)."""

import unittest

from services.pnl_rules import (
    FlatPerCategoryTaxModel,
    SavingsCombinedTaxModel,
    TaxBracket,
    get_tax_model,
)


class TestSavingsCombinedTaxModel(unittest.TestCase):
    """Spain: gains + dividends share progressive brackets, split proportionally."""

    def setUp(self):
        self.model = SavingsCombinedTaxModel()
        self.brackets = [
            TaxBracket("capital_gains", 0, 6000, 0.19),
            TaxBracket("capital_gains", 6000, 50000, 0.21),
            TaxBracket("capital_gains", 50000, None, 0.23),
        ]

    def test_zero_base(self):
        result = self.model.compute({"capital_gains": 0, "dividends": 0}, self.brackets)
        self.assertEqual(result.total_tax_owed, 0.0)
        self.assertEqual(result.combined_base, 0.0)

    def test_single_bracket(self):
        result = self.model.compute({"capital_gains": 3000, "dividends": 0}, self.brackets)
        self.assertAlmostEqual(result.total_tax_owed, 570.0)  # 3000 * 0.19
        assert result.combined_base is not None
        self.assertAlmostEqual(result.combined_base, 3000.0)

    def test_two_brackets(self):
        result = self.model.compute({"capital_gains": 10000, "dividends": 0}, self.brackets)
        # 6000 * 0.19 + 4000 * 0.21 = 1140 + 840 = 1980
        self.assertAlmostEqual(result.total_tax_owed, 1980.0)

    def test_proportional_split(self):
        result = self.model.compute(
            {"capital_gains": 3000, "dividends": 3000},
            self.brackets,
        )
        # Combined = 6000, tax = 6000 * 0.19 = 1140
        self.assertAlmostEqual(result.total_tax_owed, 1140.0)
        # Split 50/50
        self.assertAlmostEqual(result.tax_owed["capital_gains"], 570.0)
        self.assertAlmostEqual(result.tax_owed["dividends"], 570.0)

    def test_asymmetric_split(self):
        result = self.model.compute(
            {"capital_gains": 1000, "dividends": 3000},
            self.brackets,
        )
        # Combined = 4000, tax = 4000 * 0.19 = 760
        self.assertAlmostEqual(result.total_tax_owed, 760.0)
        # gains: 760 * (1000/4000) = 190
        self.assertAlmostEqual(result.tax_owed["capital_gains"], 190.0)
        # dividends: 760 * (3000/4000) = 570
        self.assertAlmostEqual(result.tax_owed["dividends"], 570.0)


class TestFlatPerCategoryTaxModel(unittest.TestCase):
    """Japan: flat rate per category, no combining."""

    def setUp(self):
        self.model = FlatPerCategoryTaxModel()
        self.brackets = [
            TaxBracket("capital_gains", 0, None, 0.20315),
            TaxBracket("dividends", 0, None, 0.20315),
        ]

    def test_zero_base(self):
        result = self.model.compute({"capital_gains": 0}, self.brackets)
        self.assertEqual(result.total_tax_owed, 0.0)
        self.assertIsNone(result.combined_base)

    def test_flat_single_category(self):
        result = self.model.compute({"capital_gains": 10000}, self.brackets)
        self.assertAlmostEqual(result.total_tax_owed, 2031.5)  # 10000 * 0.20315

    def test_flat_two_categories(self):
        result = self.model.compute(
            {"capital_gains": 10000, "dividends": 5000},
            self.brackets,
        )
        # 10000 * 0.20315 + 5000 * 0.20315 = 2031.5 + 1015.75 = 3047.25
        self.assertAlmostEqual(result.total_tax_owed, 3047.25)

    def test_missing_category_no_tax(self):
        result = self.model.compute({"capital_gains": 10000}, self.brackets)
        self.assertAlmostEqual(result.tax_owed["capital_gains"], 2031.5)


class TestGetTaxModel(unittest.TestCase):
    def test_spain_returns_savings_combined(self):
        model = get_tax_model("spain")
        self.assertIsInstance(model, SavingsCombinedTaxModel)

    def test_japan_returns_flat(self):
        model = get_tax_model("japan")
        self.assertIsInstance(model, FlatPerCategoryTaxModel)

    def test_default_returns_savings_combined(self):
        model = get_tax_model("default")
        self.assertIsInstance(model, SavingsCombinedTaxModel)

    def test_unknown_returns_flat(self):
        model = get_tax_model("nonexistent")
        self.assertIsInstance(model, FlatPerCategoryTaxModel)


if __name__ == "__main__":
    unittest.main()
