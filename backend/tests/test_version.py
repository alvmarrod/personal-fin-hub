import tomllib
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.version import router

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1")
client = TestClient(test_app)


class TestVersionEndpoint(unittest.TestCase):
    def test_reports_the_pyproject_version(self):
        resp = client.get("/api/v1/version")
        self.assertEqual(resp.status_code, 200)
        expected = tomllib.loads(PYPROJECT.read_text())["project"]["version"]
        self.assertEqual(resp.json(), {"version": expected})
