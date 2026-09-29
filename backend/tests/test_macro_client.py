"""Tests for the macro provider clients and parsers (Phase 1)."""

import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.macro_client import (
    BlsClient,
    BojClient,
    ECBClient,
    ECBDataClient,
    EurostatClient,
    FredClient,
    InvestingClient,
    MacroClientError,
    MacroParseError,
    Observation,
    _parse_date,
    _parse_number,
    change_points_only,
    parse_bls_json,
    parse_boj_json,
    parse_ecb_json,
    parse_ecb_sdmx_json,
    parse_eurostat_json,
    parse_fred_csv,
    parse_investing_html,
    yoy_from_level,
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


MACRO = FIXTURES / "macro"


class TestOfficialSourceParsers(unittest.TestCase):
    def test_boj_m2_monthly_level(self):
        payload = json.loads((MACRO / "boj_m2.json").read_text())
        observations = parse_boj_json(payload)
        self.assertGreater(len(observations), 12)
        by_date = {o.obs_date: o.value for o in observations}
        # Monthly level values (100 million yen), not a growth rate.
        self.assertIn(date(2023, 1, 1), by_date)
        self.assertTrue(all(v > 100 for v in by_date.values()))

    def test_boj_policy_change_points(self):
        payload = json.loads((MACRO / "boj_policy_rate.json").read_text())
        daily = parse_boj_json(payload)
        self.assertEqual(len(daily), 120)
        points = change_points_only(daily)
        # Window has changes 1 -> 1.25 -> 1.5.
        self.assertEqual([v for _, v in [(o.obs_date, o.value) for o in points]], [1.0, 1.25, 1.5])

    def test_yoy_from_level(self):
        levels = [
            Observation(date(2024, 1, 1), 100.0),
            Observation(date(2024, 2, 1), 110.0),
            Observation(date(2025, 1, 1), 110.0),
            Observation(date(2025, 2, 1), 121.0),
        ]
        yoy = {o.obs_date: o.value for o in yoy_from_level(levels)}
        self.assertAlmostEqual(yoy[date(2025, 1, 1)], 10.0, places=6)
        self.assertAlmostEqual(yoy[date(2025, 2, 1)], 10.0, places=6)

    def test_bls_index_then_yoy(self):
        payload = json.loads((MACRO / "bls_cpi.json").read_text())
        levels = parse_bls_json(payload)
        by_date = {o.obs_date: o.value for o in levels}
        self.assertEqual(by_date[date(2026, 8, 1)], 334.980)
        # Every parsed row is a real month (M13 annual averages are skipped).
        self.assertTrue(all(1 <= o.obs_date.month <= 12 for o in levels))
        yoy = {o.obs_date: o.value for o in yoy_from_level(levels)}
        # 2025-08 exists; 2024-08 also in window -> a YoY value is produced.
        self.assertIn(date(2025, 8, 1), yoy)

    def test_fred_csv_level(self):
        observations = parse_fred_csv((MACRO / "fred_m2sl.csv").read_text())
        by_date = {o.obs_date: o.value for o in observations}
        self.assertGreater(len(observations), 5)
        self.assertTrue(all(v > 1000 for v in by_date.values()))

    def test_eurostat_jsonstat(self):
        payload = json.loads((MACRO / "eurostat_hicp.json").read_text())
        observations = parse_eurostat_json(payload)
        by_date = {o.obs_date: o.value for o in observations}
        self.assertEqual(by_date[date(2024, 1, 1)], 2.8)
        self.assertEqual(by_date[date(2025, 12, 1)], 2.0)
        self.assertEqual(len(observations), 24)


class TestOfficialSourceClients(unittest.TestCase):
    def test_boj_client_change_points_for_policy(self):
        client = BojClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((MACRO / "boj_policy_rate.json").read_text())
            with patch.object(client, "_get", return_value=response):
                obs = client.fetch("https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=IR01&code=MADR1Z%40D")
            self.assertEqual([o.value for o in obs], [1.0, 1.25, 1.5])
        finally:
            client.close()

    def test_boj_client_yoy_for_m2(self):
        client = BojClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((MACRO / "boj_m2.json").read_text())
            with patch.object(client, "_get", return_value=response):
                obs = client.fetch("https://www.stat-search.boj.or.jp/api/v1/getDataCode?db=MD02&code=MAM1NAM2M2MO")
            # M2 level series is converted to a YoY growth rate (percent).
            self.assertGreater(len(obs), 12)
            self.assertTrue(all(0 < o.value < 50 for o in obs))
        finally:
            client.close()

    def test_bls_client_returns_yoy(self):
        client = BlsClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((MACRO / "bls_cpi.json").read_text())
            with patch.object(client, "_post", return_value=response):
                obs = client.fetch("https://api.bls.gov/publicAPI/v2/timeseries/data/")
            # YoY values are small percentages, not index levels.
            self.assertTrue(all(abs(o.value) < 50 for o in obs))
        finally:
            client.close()

    def test_fred_client(self):
        client = FredClient()
        try:
            response = MagicMock()
            response.text = (MACRO / "fred_m2sl.csv").read_text()
            with patch.object(client, "_get", return_value=response):
                obs = client.fetch("https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL")
            self.assertGreater(len(obs), 5)
        finally:
            client.close()

    def test_eurostat_client(self):
        client = EurostatClient()
        try:
            response = MagicMock()
            response.json.return_value = json.loads((MACRO / "eurostat_hicp.json").read_text())
            with patch.object(client, "_get", return_value=response):
                obs = client.fetch("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr")
            self.assertEqual(len(obs), 24)
        finally:
            client.close()

    def test_fetch_series_dispatches_new_providers(self):
        from services.macro_client import fetch_series

        cases = {
            "boj": BojClient,
            "bls": BlsClient,
            "fred": FredClient,
            "eurostat": EurostatClient,
        }
        for provider, cls in cases.items():
            with self.subTest(provider=provider):
                with patch.object(cls, "fetch", return_value=[Observation(date(2025, 1, 1), 1.0)]) as m:
                    result = fetch_series(provider, "https://example.invalid/x")
                self.assertEqual(result, [Observation(date(2025, 1, 1), 1.0)])
                m.assert_called_once()

    def test_unknown_provider_raises(self):
        from services.macro_client import fetch_series

        with self.assertRaises(MacroClientError):
            fetch_series("nope", "https://example.invalid/x")
