import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.backups import router
from services import activity_svc, backup_svc


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, total_value REAL);
        INSERT INTO profiles (name) VALUES ('Default');
        INSERT INTO entities (name) VALUES ('Bank');
        INSERT INTO transactions (total_value) VALUES (1000);
    """)
    conn.commit()
    conn.close()


app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)


class BackupRoutesTest(unittest.TestCase):
    def setUp(self):
        activity_svc.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "finhub.db"
        self.backup_dir = self.root / "backups"
        self.backup_dir.mkdir()
        _make_db(self.db)

        self.patchers: list[Any] = [
            patch.object(backup_svc, "DB_PATH", self.db),
            patch.dict(
                os.environ,
                {"BACKUP_DIR": str(self.backup_dir), "BACKUP_RETENTION": "3", "BACKUP_TIMEZONE": "UTC"},
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        activity_svc.reset()
        self.tmp.cleanup()

    def _create(self, tag: str = "manual", name: str | None = None) -> Path:
        patcher = (
            patch.object(backup_svc, "_filename", return_value=name)
            if name
            else patch.object(backup_svc, "_filename", wraps=backup_svc._filename)
        )
        with patcher:
            return backup_svc.create_backup(tag)

    # -- list ----------------------------------------------------------------

    def test_list_returns_policy_and_items(self):
        self._create("daily", "finhub.db-20260101-030000.bak")
        self._create("manual", "finhub.db-20260102-030000.bak")

        resp = client.get("/api/v1/backups")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["policy"]["retention"], 3)
        self.assertTrue(body["policy"]["enabled"])
        self.assertEqual(
            [item["name"] for item in body["items"]],
            [
                "finhub.db-20260102-030000.bak",
                "finhub.db-20260101-030000.bak",
            ],
        )
        self.assertTrue(body["items"][0]["latest"])
        self.assertEqual(body["items"][1]["tag"], "daily")

    def test_list_empty_directory(self):
        resp = client.get("/api/v1/backups")
        self.assertEqual(resp.json()["items"], [])

    # -- create --------------------------------------------------------------

    def test_create_returns_created_and_pruned(self):
        with patch.object(backup_svc, "_filename", return_value="finhub.db-20260101-000000.bak"):
            backup_svc.create_backup("daily")
        with (
            patch.dict(os.environ, {"BACKUP_RETENTION": "1"}),
            patch.object(backup_svc, "_filename", return_value="finhub.db-20260102-000000.bak"),
        ):
            resp = client.post("/api/v1/backups")

        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["created"]["name"], "finhub.db-20260102-000000.bak")
        self.assertEqual(body["pruned"], ["finhub.db-20260101-000000.bak"])
        self.assertEqual(len(list(self.backup_dir.glob("finhub.db-*.bak"))), 1)

    # -- download ------------------------------------------------------------

    def test_download_returns_the_file(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")

        resp = client.get(f"/api/v1/backups/{path.name}")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, path.read_bytes())

    def test_download_rejects_unknown_names(self):
        self.assertEqual(client.get("/api/v1/backups/not-a-backup.bak").status_code, 404)
        self.assertEqual(client.get("/api/v1/backups/..%2Ffinhub.db").status_code, 404)

    # -- inspect -------------------------------------------------------------

    def test_inspect_accepts_a_valid_backup(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")

        resp = client.post(
            "/api/v1/backups/inspect",
            content=path.read_bytes(),
            headers={"X-Filename": path.name, "Content-Type": "application/octet-stream"},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["name"], path.name)
        self.assertEqual(body["created_at"], "2026-01-01T03:00:00+00:00")
        self.assertTrue(body["migrations"])

    def test_inspect_rejects_garbage(self):
        resp = client.post(
            "/api/v1/backups/inspect",
            content=b"definitely not sqlite",
            headers={"X-Filename": "junk.bak"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_inspect_rejects_a_newer_schema(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT)")
        conn.execute("INSERT INTO schema_migrations (version) VALUES ('9999_from_the_future')")
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/v1/backups/inspect",
            content=path.read_bytes(),
            headers={"X-Filename": path.name},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("newer version", resp.json()["detail"])

    def test_inspect_rejects_oversized_uploads(self):
        with patch("routes.backups.MAX_UPLOAD_BYTES", 4):
            resp = client.post("/api/v1/backups/inspect", content=b"12345")
        self.assertEqual(resp.status_code, 413)

    # -- restore -------------------------------------------------------------

    def test_restore_refuses_while_work_is_running(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")
        running = [{"name": "Price sync", "started_at": "2026-01-01T03:00:00+00:00"}]

        with patch("services.activity_svc.running", return_value=running):
            resp = client.post(f"/api/v1/backups/{path.name}/restore")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["detail"]["activity"], running)

    def test_restore_existing_delegates(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")
        result = {"restored": path.name, "pre_restore": "x", "pruned": [], "migrations": []}

        with patch("routes.backups.restore_svc.restore", return_value=result) as restore:
            resp = client.post(f"/api/v1/backups/{path.name}/restore")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), result)
        restore.assert_called_once()

    def test_restore_upload_delegates(self):
        path = self._create("manual", "finhub.db-20260101-030000.bak")
        result = {"restored": "upload.bak", "pre_restore": "x", "pruned": [], "migrations": []}

        with patch("routes.backups.restore_svc.restore", return_value=result) as restore:
            resp = client.post(
                "/api/v1/backups/restore",
                content=path.read_bytes(),
                headers={"X-Filename": "upload.bak"},
            )

        self.assertEqual(resp.status_code, 200)
        restore.assert_called_once()
        self.assertEqual(list(self.backup_dir.glob(".upload-*")), [])

    def test_restore_unknown_name_returns_404(self):
        self.assertEqual(client.post("/api/v1/backups/nope.bak/restore").status_code, 404)


if __name__ == "__main__":
    unittest.main()
