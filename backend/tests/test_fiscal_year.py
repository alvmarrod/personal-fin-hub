import unittest
from datetime import date, datetime

from services.pnl_rules import fiscal_year_bounds


class TestFiscalYearBounds(unittest.TestCase):
    def test_natural_year(self):
        fy = fiscal_year_bounds(datetime(2025, 6, 1), (1, 1))
        self.assertEqual(fy.label, 2025)
        self.assertEqual(fy.start_date, date(2025, 1, 1))
        self.assertEqual(fy.end_date, date(2025, 12, 31))

    def test_natural_year_year_boundary(self):
        self.assertEqual(fiscal_year_bounds(datetime(2025, 1, 1), (1, 1)).label, 2025)
        self.assertEqual(fiscal_year_bounds(datetime(2025, 12, 31), (1, 1)).label, 2025)

    def test_april_start(self):
        fy = fiscal_year_bounds(datetime(2025, 6, 1), (4, 1))
        self.assertEqual(fy.label, 2025)
        self.assertEqual(fy.start_date, date(2025, 4, 1))
        self.assertEqual(fy.end_date, date(2026, 3, 31))

    def test_april_start_before_cutoff(self):
        fy = fiscal_year_bounds(datetime(2025, 2, 1), (4, 1))
        self.assertEqual(fy.label, 2024)
        self.assertEqual(fy.start_date, date(2024, 4, 1))
        self.assertEqual(fy.end_date, date(2025, 3, 31))


if __name__ == "__main__":
    unittest.main()
