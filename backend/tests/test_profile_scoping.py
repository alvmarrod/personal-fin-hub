import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from db import queries
from db.connection import get_db
from routes import entities
from routes.deps import require_profile

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def make_app():
    app = FastAPI()
    app.include_router(entities.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
    return app


class TestProfileScoping(unittest.TestCase):
    """End-to-end profile isolation through the API layer.

    Uses a temporary file-backed DB with the real ``get_db`` so the full
    ContextVar -> connection -> query scoping path is exercised.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "scoping.db")
        self.patcher = patch("db.connection.DB_PATH", self.db_path)
        self.patcher.start()

        conn = get_db()
        conn.executescript(SCHEMA_PATH.read_text())
        self.profile_a = queries.create_profile(conn, "Alpha", None)
        self.profile_b = queries.create_profile(conn, "Beta", None)
        conn.commit()
        conn.close()

        self.client = TestClient(make_app())
        self.headers_a = {"X-Profile-ID": str(self.profile_a)}
        self.headers_b = {"X-Profile-ID": str(self.profile_b)}

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_entity(self, name, headers):
        return self.client.post("/api/v1/entities", json={"name": name, "entity_type": "BROKER"}, headers=headers)

    def test_missing_header_401(self):
        resp = self.client.get("/api/v1/entities")
        self.assertEqual(resp.status_code, 401)

    def test_unknown_profile_404(self):
        resp = self.client.get("/api/v1/entities", headers={"X-Profile-ID": "999"})
        self.assertEqual(resp.status_code, 404)

    def test_create_scopes_row_to_profile(self):
        resp = self._create_entity("Broker A", self.headers_a)
        self.assertEqual(resp.status_code, 201)
        conn = get_db()
        try:
            row = conn.execute("SELECT profile_id FROM entities WHERE name = ?", ("Broker A",)).fetchone()
            self.assertEqual(row["profile_id"], self.profile_a)
        finally:
            conn.close()

    def test_entity_invisible_to_other_profile(self):
        self._create_entity("Broker A", self.headers_a)
        resp = self.client.get("/api/v1/entities", headers=self.headers_b)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_entity_visible_to_own_profile(self):
        self._create_entity("Broker A", self.headers_a)
        resp = self.client.get("/api/v1/entities", headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e["name"] for e in resp.json()], ["Broker A"])

    def test_get_single_cross_profile_404(self):
        created = self._create_entity("Broker A", self.headers_a)
        eid = created.json()["id"]
        resp = self.client.get(f"/api/v1/entities/{eid}", headers=self.headers_b)
        self.assertEqual(resp.status_code, 404)

    def test_profiles_do_not_leak_across_requests(self):
        self._create_entity("Broker A", self.headers_a)
        self.client.get("/api/v1/entities", headers=self.headers_b)
        resp = self.client.get("/api/v1/entities", headers=self.headers_a)
        self.assertEqual([e["name"] for e in resp.json()], ["Broker A"])

    def test_unscoped_call_after_scoped_request(self):
        """A direct (non-API) unscoped connection must still see all rows."""
        self._create_entity("Broker A", self.headers_a)
        conn = get_db()
        try:
            rows = queries.get_all_entities(conn)
            self.assertEqual(len(rows), 1)
        finally:
            conn.close()
