import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from services import restore_svc
from services.backup_svc import BackupError


def _make_db(path: Path, marker: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(f"""
        CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, total_value REAL);
        INSERT INTO profiles (name) VALUES ('{marker}');
    """)
    conn.commit()
    conn.close()


class RestoreServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "finhub.db"
        self.backup_dir = self.root / "backups"
        self.backup_dir.mkdir()
        _make_db(self.db, "current")

        self.restore = self.root / "backups" / "finhub.db-20260101-030000.bak"
        _make_db(self.restore, "restored")

        self.patchers: list[Any] = [
            patch.object(restore_svc.backup_svc, "DB_PATH", self.db),
            patch.dict(
                os.environ,
                {"BACKUP_DIR": str(self.backup_dir), "BACKUP_RETENTION": "3", "BACKUP_TIMEZONE": "UTC"},
            ),
            patch.object(restore_svc, "_pause_scheduler"),
            patch.object(restore_svc, "_resume_scheduler"),
            patch.object(restore_svc, "_apply_migrations", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def _profile(self, path: Path) -> str:
        conn = sqlite3.connect(path)
        try:
            return conn.execute("SELECT name FROM profiles").fetchone()[0]
        finally:
            conn.close()

    def test_restore_replaces_content_and_keeps_a_pre_restore_copy(self):
        result = restore_svc.restore(self.restore)

        self.assertEqual(self._profile(self.db), "restored")
        pre = self.backup_dir / str(result["pre_restore"])
        self.assertTrue(pre.exists())
        self.assertEqual(self._profile(pre), "current")

    def test_restore_refuses_while_background_work_runs(self):
        running = [{"name": "Price sync", "started_at": "now"}]
        with (
            patch("services.activity_svc.running", return_value=running),
            self.assertRaises(restore_svc.RestoreBusy) as ctx,
        ):
            restore_svc.restore(self.restore)

        self.assertEqual(ctx.exception.running[0]["name"], "Price sync")
        self.assertEqual(self._profile(self.db), "current")

    def test_restore_rejects_an_invalid_file(self):
        bad = self.backup_dir / "finhub.db-20260101-040000.bak"
        bad.write_bytes(b"not sqlite")
        with self.assertRaises(BackupError):
            restore_svc.restore(bad)
        self.assertEqual(self._profile(self.db), "current")

    def test_restore_clears_the_maintenance_window(self):
        restore_svc.restore(self.restore)
        from services import activity_svc

        self.assertFalse(activity_svc.in_maintenance())

    def test_restore_stops_the_scheduler_before_touching_the_database(self):
        order = []

        def pause():
            order.append("pause")

        def copy(path, dest=None):
            order.append("copy")

        with (
            patch.object(restore_svc, "_pause_scheduler", side_effect=pause),
            patch.object(restore_svc.backup_svc, "restore_from_backup", side_effect=copy),
        ):
            restore_svc.restore(self.restore)

        self.assertEqual(order, ["pause", "copy"])

    def test_restore_never_prunes_the_backup_it_reads(self):
        older = self.backup_dir / "finhub.db-20251231-030000.bak"
        _make_db(older, "older")

        with patch.dict(os.environ, {"BACKUP_RETENTION": "1"}):
            result = restore_svc.restore(self.restore)

        pruned = cast(list[str], result["pruned"])
        self.assertEqual(self._profile(self.db), "restored")
        self.assertTrue(self.restore.exists())
        self.assertIn(older.name, pruned)
        self.assertNotIn(self.restore.name, pruned)

    def test_maintenance_manifest_entry_is_written(self):
        result = restore_svc.restore(self.restore)
        manifest = json.loads((self.backup_dir / "manifest.json").read_text())

        self.assertEqual(manifest["entries"][str(result["pre_restore"])]["tag"], "pre-restore")


if __name__ == "__main__":
    unittest.main()
