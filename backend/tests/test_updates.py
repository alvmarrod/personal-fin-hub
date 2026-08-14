import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.updates import router as updates_router
from services import update_svc
from services.update_svc import (
    _BACKEND_VERSION,
    get_update_status,
    latest_by_prefix,
    max_version,
    parse_version,
)

app = FastAPI()
app.include_router(updates_router, prefix="/api/v1")
client = TestClient(app)

RELEASES = [
    {"tag_name": "frontend/v0.9.0"},
    {"tag_name": "frontend/v0.8.2"},
    {"tag_name": "backend/v0.11.0"},
    {"tag_name": "backend/v0.10.3"},
    {"tag_name": "v0.6.0"},
]


class _ConfigGuard:
    """Temporarily override update_check config values and restore on exit."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = None

    def __enter__(self):
        self.saved = dict(update_svc.config._data or {})
        data = dict(self.saved)
        data["update_check"] = {**data.get("update_check", {}), **self.overrides}
        update_svc.config._data = data
        return self

    def __exit__(self, *exc):
        update_svc.config._data = self.saved


class TestSemver(unittest.TestCase):
    def test_parse_version_strips_prefix(self):
        self.assertEqual(parse_version("backend/v0.11.0"), (0, 11, 0))
        self.assertEqual(parse_version("v0.9.0"), (0, 9, 0))
        self.assertEqual(parse_version("0.11.0"), (0, 11, 0))

    def test_parse_version_orders_correctly(self):
        self.assertLess(parse_version("0.9.0"), parse_version("0.10.0"))
        self.assertLess(parse_version("0.10.0"), parse_version("0.11.0"))
        self.assertLess(parse_version("0.11.0"), parse_version("0.11.1"))

    def test_parse_version_garbage_sorts_low(self):
        self.assertEqual(parse_version("not-a-version"), (0,))
        self.assertLess(parse_version("garbage"), parse_version("0.0.1"))

    def test_max_version(self):
        self.assertEqual(
            max_version(["0.9.0", "0.10.3", "0.11.0", "0.8.1"]),
            "0.11.0",
        )
        self.assertIsNone(max_version([]))


class TestReleaseSelection(unittest.TestCase):
    def test_latest_by_prefix(self):
        self.assertEqual(latest_by_prefix(RELEASES, "backend/"), "backend/v0.11.0")
        self.assertEqual(latest_by_prefix(RELEASES, "frontend/"), "frontend/v0.9.0")
        self.assertIsNone(latest_by_prefix(RELEASES, "market/"))

    def test_ignores_unprefixed_legacy_tags(self):
        releases = [{"tag_name": "v0.6.0"}, {"tag_name": "backend/v0.11.0"}]
        self.assertEqual(latest_by_prefix(releases, "backend/"), "backend/v0.11.0")


class TestGetUpdateStatus(unittest.TestCase):
    def setUp(self):
        update_svc.reset_cache()

    def tearDown(self):
        update_svc.reset_cache()

    def test_reports_versions_and_outdated(self):
        releases = [*RELEASES, {"tag_name": "backend/v999.0.0"}, {"tag_name": "frontend/v999.0.0"}]
        with patch("services.update_svc._fetch_releases", return_value=releases):
            result = get_update_status(frontend_version="0.9.0")

        self.assertTrue(result["enabled"])
        self.assertEqual(result["backend"]["current"], _BACKEND_VERSION)
        self.assertEqual(result["backend"]["latest"], "999.0.0")
        self.assertTrue(result["backend"]["outdated"])
        self.assertEqual(
            result["backend"]["url"],
            "https://github.com/alvmarrod/personal-fin-hub/releases/tag/backend/v999.0.0",
        )
        self.assertEqual(result["frontend"]["current"], "0.9.0")
        self.assertEqual(result["frontend"]["latest"], "999.0.0")
        self.assertTrue(result["frontend"]["outdated"])

    def test_up_to_date_when_latest_equals_current(self):
        with patch("services.update_svc._fetch_releases", return_value=RELEASES):
            result = get_update_status(frontend_version="0.9.0")

        self.assertEqual(result["backend"]["latest"], "0.11.0")
        self.assertFalse(result["backend"]["outdated"])
        self.assertEqual(result["frontend"]["latest"], "0.9.0")
        self.assertFalse(result["frontend"]["outdated"])

    def test_frontend_null_without_version(self):
        with patch("services.update_svc._fetch_releases", return_value=RELEASES):
            result = get_update_status()

        self.assertIsNone(result["frontend"])
        self.assertIsNotNone(result["backend"])

    def test_disabled_returns_enabled_false_no_fetch(self):
        with (
            _ConfigGuard(enabled=False),
            patch("services.update_svc._fetch_releases") as mock_fetch,
        ):
            result = get_update_status(frontend_version="0.9.0")

        self.assertEqual(result, {"enabled": False})
        mock_fetch.assert_not_called()

    def test_fail_open_on_error(self):
        with patch("services.update_svc._fetch_releases", side_effect=ConnectionError("down")):
            result = get_update_status(frontend_version="0.9.0")

        self.assertTrue(result["enabled"])
        self.assertEqual(result["error"], "unavailable")
        self.assertIsNone(result["backend"])
        self.assertIsNone(result["frontend"])

    def test_cached_within_ttl(self):
        with patch("services.update_svc._fetch_releases", return_value=RELEASES) as mock_fetch:
            get_update_status(frontend_version="0.9.0")
            get_update_status(frontend_version="0.9.0")

        self.assertEqual(mock_fetch.call_count, 1)

    def test_cache_expiry_refetches(self):
        with (
            _ConfigGuard(cache_seconds=0),
            patch("services.update_svc._fetch_releases", return_value=RELEASES) as mock_fetch,
        ):
            get_update_status(frontend_version="0.9.0")
            get_update_status(frontend_version="0.9.0")

        self.assertEqual(mock_fetch.call_count, 2)


class TestUpdatesEndpoint(unittest.TestCase):
    def setUp(self):
        update_svc.reset_cache()

    def tearDown(self):
        update_svc.reset_cache()

    def test_endpoint_shape(self):
        with patch("services.update_svc._fetch_releases", return_value=RELEASES):
            resp = client.get("/api/v1/updates?frontend_version=0.9.0")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["enabled"])
        self.assertIn("checked_at", data)
        self.assertEqual(data["backend"]["current"], _BACKEND_VERSION)
        self.assertEqual(data["frontend"]["current"], "0.9.0")

    def test_endpoint_is_public(self):
        with patch("services.update_svc._fetch_releases", return_value=RELEASES):
            resp = client.get("/api/v1/updates")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["frontend"])

    def test_endpoint_disabled(self):
        with _ConfigGuard(enabled=False):
            resp = client.get("/api/v1/updates")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"enabled": False})


if __name__ == "__main__":
    unittest.main()
