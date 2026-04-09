import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import httpx

from services.api_client import (
    MarketAPIClient,
    MarketAPIError,
    MarketAPIUnavailable,
    MarketAPINotFound,
)


class TestMarketAPIClient(unittest.TestCase):
    def setUp(self):
        self.mock_client_patcher = patch("services.api_client.httpx.Client")
        self.MockClient = self.mock_client_patcher.start()
        self.mock_instance = MagicMock()
        self.MockClient.return_value = self.mock_instance

    def tearDown(self):
        self.mock_client_patcher.stop()

    def test_get_price_success(self):
        mock_response = {"price": 150.25}
        self.mock_instance.request.return_value.json.return_value = mock_response
        self.mock_instance.request.return_value.raise_for_status = MagicMock()

        client = MarketAPIClient(base_url="http://test")
        result = client.get_price("AAPL")

        self.assertEqual(result, {"price": 150.25})

    def test_get_price_api_unavailable(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(
            message="Connection failed", request=MagicMock()
        )

        client = MarketAPIClient(base_url="http://test")

        with self.assertRaises(MarketAPIUnavailable):
            client.get_price("AAPL")

    def test_get_price_timeout(self):
        self.mock_instance.request.side_effect = httpx.TimeoutException(
            message="Timeout", request=MagicMock()
        )

        client = MarketAPIClient(base_url="http://test")

        with self.assertRaises(MarketAPIUnavailable):
            client.get_price("AAPL")

    def test_get_field_success(self):
        mock_response = {"ROE": 1.5}
        self.mock_instance.request.return_value.json.return_value = mock_response
        self.mock_instance.request.return_value.raise_for_status = MagicMock()

        client = MarketAPIClient(base_url="http://test")
        result = client.get_field("AAPL", "ROE")

        self.assertEqual(result, {"ROE": 1.5})

    def test_get_field_not_found(self):
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=error_response
        )
        self.mock_instance.request.return_value = error_response

        client = MarketAPIClient(base_url="http://test")

        with self.assertRaises(MarketAPINotFound):
            client.get_field("INVALID", "ROE")

    def test_get_all_success(self):
        mock_response = {"price": 150, "marketCap": "3T", "pe": 25}
        self.mock_instance.request.return_value.json.return_value = mock_response
        self.mock_instance.request.return_value.raise_for_status = MagicMock()

        client = MarketAPIClient(base_url="http://test")
        result = client.get_all("AAPL")

        self.assertEqual(result, {"price": 150, "marketCap": "3T", "pe": 25})

    def test_health_check_available(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        self.mock_instance.request.return_value = mock_response

        client = MarketAPIClient(base_url="http://test")
        result = client.health_check()

        self.assertTrue(result)

    def test_health_check_unavailable(self):
        self.mock_instance.request.side_effect = httpx.ConnectError(
            message="Connection failed", request=MagicMock()
        )

        client = MarketAPIClient(base_url="http://test")
        result = client.health_check()

        self.assertFalse(result)

    def test_get_raw_field_success(self):
        self.mock_instance.get.return_value.text = "1.7432836360316066"
        self.mock_instance.get.return_value.raise_for_status = MagicMock()

        client = MarketAPIClient(base_url="http://test")
        result = client.get_raw_field("AAPL", "ROE")

        self.assertEqual(result, "1.7432836360316066")

    def test_get_price_general_error(self):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Error", request=MagicMock(), response=error_response
        )
        self.mock_instance.request.return_value = error_response

        client = MarketAPIClient(base_url="http://test")

        with self.assertRaises(MarketAPIError):
            client.get_price("AAPL")


if __name__ == "__main__":
    unittest.main()
