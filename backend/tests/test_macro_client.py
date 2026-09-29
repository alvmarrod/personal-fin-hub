"""Tests for the macro provider clients and parsers (Phase 1)."""

import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.macro_client import (
    ECBClient,
    ECBDataClient,
    InvestingClient,
    MacroParseError,
    Observation,
    _parse_date,
    _parse_number,
    parse_ecb_json,
    parse_ecb_sdmx_json,
    parse_investing_html,
)

FIXTURES = Path(__file__).parent / "fixtures"
INVESTING = FIXTURES / "investing"
ECB = FIXTURES / "ecb"


def load_html(name: str) -> str:
    return (INVESTING / name).read_text(encoding="utf-8", errors="replace")


class TestValueParsing(unittest.TestCase):
    def test_number_passthrough(self):
        self.assertEqual(_parse_number(3.2), 3.2)
        self.assertEqual(_parse_number(1), 1.0)

    def test_percentage_strings(self):
        self.assertEqual(_parse_number("1.00%"), 1.00)
        self.assertEqual(_parse_number("-0.10%"), -0.10)
        self.assertEqual(_parse_number("3.2"), 3.2)

    def test_placeholders_are_none(self):
        self.assertIsNone(_parse_number("-"))
        self.assertIsNone(_parse_number("--"))
        self.assertIsNone(_parse_number(""))
        self.assertIsNone(_parse_number(None))

    def test_date_from_iso_and_period(self):
        self.assertEqual(_parse_date("2026-09-17T09:00:00Z"), date(2026, 9, 17))
        self.assertEqual(_parse_date("2026-09-17"), date(2026, 9, 17))
        self.assertEqual(_parse_date("2026-09"), date(2026, 9, 1))
        self.assertEqual(_parse_date("2026"), date(2026, 1, 1))
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date("not a date"))


class TestParseInvestingHtml(unittest.TestCase):
    def test_parses_all_seven_fixtures(self):
        fixtures = {
            "cpi-68.html": "eurozone-cpi",
            "cpi-733.html": "usa-cpi",
            "boj-interest-rate-decision-165.html": "boj",
            "interest-rate-decision-164.html": "ecb-deposit",
            "japan-cpi-yoy-992.html": "japan-cpi",
            "m2-money-stock-366.html": "japan-m2",
            "us-m2-money-supply-1999.html": "usa-m2",
        }
        for filename, label in fixtures.items():
            with self.subTest(fixture=label):
                observations = parse_investing_html(load_html(filename))
                self.assertGreater(len(observations), 0)
                self.assertTrue(all(isinstance(o, Observation) for o in observations))
                # Dates ascending after sort; values are floats.
                dates = sorted(o.obs_date for o in observations)
                self.assertEqual(dates[0], min(dates))
                self.assertTrue(all(isinstance(o.value, float) for o in observations))

    def test_skips_releases_without_actual(self):
        html = load_html("cpi-68.html")
        observations = parse_investing_html(html)
        # The fixture has 100 occurrences, 98 with an actual value.
        self.assertEqual(len(observations), 98)

    def test_missing_next_data_raises(self):
        with self.assertRaises(MacroParseError):
            parse_investing_html("<html><body>no island</body></html>")

    def test_expected_first_value(self):
        observations = parse_investing_html(load_html("cpi-68.html"))
        by_date = {o.obs_date: o.value for o in observations}
        self.assertEqual(by_date[date(2026, 9, 17)], 3.2)


class TestParseEcbJson(unittest.TestCase):
    def test_parses_fixture(self):
        payload = json.loads((ECB / "eurozone-m2-yoy.json").read_text())
        observations = parse_ecb_json(payload)
        by_date = {o.obs_date: o.value for o in observations}
        self.assertEqual(by_date[date(2026, 8, 1)], 3.2)
        self.assertEqual(by_date[date(2026, 7, 1)], 3.3)
        # The missing-value row is skipped.
        self.assertNotIn(date(2026, 6, 1), by_date)
        self.assertEqual(len(observations), 2)

    def test_wrapped_payload(self):
        payload = {"data": [{"PERIOD": "2026-08", "OBS": 3.2}]}
        self.assertEqual(parse_ecb_json(payload), [Observation(date(2026, 8, 1), 3.2)])

    def test_non_list_raises(self):
        with self.assertRaises(MacroParseError):
            parse_ecb_json("not a list")

    def test_unknown_dict_shape_yields_no_observations(self):
        self.assertEqual(parse_ecb_json({"nope": 1}), [])


class TestParseEcbSdmxJson(unittest.TestCase):
    def _fixture(self):
        return json.loads((ECB / "dfr-change-points.json").read_text())

    def test_parses_all_daily_points(self):
        observations = parse_ecb_sdmx_json(self._fixture())
        self.assertEqual(len(observations), 76)
        by_date = {o.obs_date: o.value for o in observations}
        self.assertEqual(by_date[date(2025, 5, 1)], 2.25)
        self.assertEqual(by_date[date(2025, 7, 15)], 2.0)

    def test_change_points_only_filters_repeats(self):
        observations = parse_ecb_sdmx_json(self._fixture(), change_points_only=True)
        # Daily series has one change in the window: 2.25 -> 2.0 on 2025-06-11.
        self.assertEqual(
            [(o.obs_date, o.value) for o in observations],
            [(date(2025, 5, 1), 2.25), (date(2025, 6, 11), 2.0)],
        )

    def test_non_dict_raises(self):
        with self.assertRaises(MacroParseError):
            parse_ecb_sdmx_json("not an object")

    def test_bad_shape_raises(self):
        with self.assertRaises(MacroParseError):
            parse_ecb_sdmx_json({"dataSets": []})


class TestClients(unittest.TestCase):
    def test_investing_client_parses_response(self):
        client = InvestingClient()
        try:
            response = MagicMock()
            response.text = load_html("cpi-68.html")
            with patch.object(client, "_get", return_value=response):
                observations = client.fetch("https://www.investing.com/economic-calendar/cpi-68")
            self.assertEqual(len(observations), 98)
        finally:
            client.close()

    def test_ecb_client_parses_response(self):
        client = ECBClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((ECB / "eurozone-m2-yoy.json").read_text())
            with patch.object(client, "_get", return_value=response):
                observations = client.fetch(
                    "https://data.ecb.europa.eu/data-detail-api/BSI.M.U2.Y.V.M20.X.I.U2.2300.Z01.A"
                )
            self.assertEqual(len(observations), 2)
        finally:
            client.close()

    def test_ecb_invalid_json_raises(self):
        client = ECBClient()
        try:
            response = MagicMock()
            response.json.side_effect = ValueError("bad json")
            with patch.object(client, "_get", return_value=response), self.assertRaises(MacroParseError):
                client.fetch("https://data.ecb.europa.eu/data-detail-api/X")
        finally:
            client.close()

    def test_ecb_data_client_returns_change_points(self):
        client = ECBDataClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((ECB / "dfr-change-points.json").read_text())
            with patch.object(client, "_get", return_value=response):
                observations = client.fetch(
                    "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=jsondata"
                )
            self.assertEqual(
                [(o.obs_date, o.value) for o in observations],
                [(date(2025, 5, 1), 2.25), (date(2025, 6, 11), 2.0)],
            )
        finally:
            client.close()

    def test_fetch_series_dispatches_ecb_data(self):
        from services.macro_client import fetch_series

        with patch.object(ECBDataClient, "fetch", return_value=[Observation(date(2025, 6, 11), 2.0)]) as m:
            result = fetch_series(
                "ecb",
                "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=jsondata",
            )
        self.assertEqual(result, [Observation(date(2025, 6, 11), 2.0)])
        m.assert_called_once()


if __name__ == "__main__":
    unittest.main()
