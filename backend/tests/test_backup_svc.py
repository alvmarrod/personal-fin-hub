import os
import sqlite3
import stat
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from services import backup_svc


def _make_source_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, total_value REAL);
        INSERT INTO profiles (name) VALUES ('Default');
        INSERT INTO entities (name) VALUES ('Bank');
        INSERT INTO transactions (total_value) VALUES (1000);
        """
    )
    conn.commit()
    conn.close()


class BackupServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "finhub.db"
        _make_source_db(self.db)
        self.backup_dir = self.root / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.patchers: list[Any] = [
            patch.object(backup_svc, "DB_PATH", self.db),
            patch.dict(
                os.environ,
                {
                    "BACKUP_DIR": str(self.backup_dir),
                    "BACKUP_TIMEZONE": "UTC",
                    "BACKUP_RETENTION": "2",
                    "BACKUP_CRON": "03:00",
                    "BACKUP_ENABLED": "1",
                },
                clear=False,
            ),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.tmp.cleanup()

    # -- create / verify ----------------------------------------------------

    def test_create_backup_makes_verified_file(self):
        path = backup_svc.create_backup("test")
        self.assertTrue(path.exists())
        self.assertRegex(path.name, r"^finhub\.db-\d{8}-\d{6}\.bak$")
        self.assertTrue(backup_svc.verify_backup(path))
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_create_backup_preserves_data(self):
        path = backup_svc.create_backup("test")
        conn = sqlite3.connect(path)
        count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_create_backup_refuses_missing_db(self):
        self.db.unlink()
        with self.assertRaises(backup_svc.BackupError):
            backup_svc.create_backup("test")

    def test_create_backup_refuses_empty_db(self):
        Path(self.db).write_bytes(b"")
        with self.assertRaises(backup_svc.BackupError):
            backup_svc.create_backup("test")

    def test_verify_backup_fails_on_garbage(self):
        junk = self.root / "junk.bak"
        junk.write_bytes(b"this is not a sqlite database")
        self.assertFalse(backup_svc.verify_backup(junk))

    # -- list / prune -------------------------------------------------------

    def test_list_backups_newest_first(self):
        for name in ["finhub.db-20260810-030000.bak", "finhub.db-20260811-030000.bak"]:
            (self.backup_dir / name).write_bytes(b"x")
        listing = [p.name for p in backup_svc.list_backups()]
        self.assertEqual(listing, ["finhub.db-20260811-030000.bak", "finhub.db-20260810-030000.bak"])

    def test_prune_keeps_retention(self):
        names = [
            "finhub.db-20260810-000001.bak",
            "finhub.db-20260810-000002.bak",
            "finhub.db-20260810-000003.bak",
            "finhub.db-20260810-000004.bak",
        ]
        with patch.object(backup_svc, "_filename", side_effect=names):
            for i in range(4):
                backup_svc.create_backup(f"run-{i}")
        pruned = backup_svc.prune_backups(2)
        self.assertEqual(len(pruned), 2)
        remaining = [p.name for p in backup_svc.list_backups()]
        self.assertEqual(remaining, list(reversed(names[2:])))
        self.assertNotIn(pruned[0].name, remaining)

    # -- daily due ----------------------------------------------------------

    def test_is_daily_due_before_cutoff(self):
        now = datetime(2026, 8, 11, 2, 59, tzinfo=UTC)
        self.assertFalse(backup_svc.is_daily_due(now))

    def test_is_daily_due_after_cutoff_no_today_backup(self):
        now = datetime(2026, 8, 11, 3, 0, tzinfo=UTC)
        self.assertTrue(backup_svc.is_daily_due(now))

    def test_is_daily_due_false_when_today_backup_exists(self):
        (self.backup_dir / "finhub.db-20260811-030000.bak").write_bytes(b"x")
        now = datetime(2026, 8, 11, 3, 0, tzinfo=UTC)
        self.assertFalse(backup_svc.is_daily_due(now))

    def test_is_daily_due_uses_backup_timezone(self):
        now_utc = datetime(2026, 8, 11, 2, 59, tzinfo=UTC)
        with patch.dict(os.environ, {"BACKUP_TIMEZONE": "Asia/Tokyo"}, clear=False):
            # 02:59 UTC == 11:59 JST -> past the 03:00 JST cutoff
            self.assertTrue(backup_svc.is_daily_due(now_utc))

    # -- startup / migration orchestration -----------------------------------

    def test_startup_daily_backup_creates_when_due(self):
        with patch.object(backup_svc, "is_daily_due", return_value=True):
            created = backup_svc.startup_daily_backup()
        self.assertTrue(created)
        self.assertEqual(len(backup_svc.list_backups()), 1)

    def test_startup_daily_backup_skips_when_not_due(self):
        with patch.object(backup_svc, "is_daily_due", return_value=False):
            created = backup_svc.startup_daily_backup()
        self.assertFalse(created)
        self.assertEqual(backup_svc.list_backups(), [])

    def test_startup_daily_backup_skips_when_disabled(self):
        with patch.object(backup_svc, "backup_enabled", return_value=False):
            created = backup_svc.startup_daily_backup()
        self.assertFalse(created)

    def test_migration_backups_skip_fresh_or_noop(self):
        self.assertEqual(backup_svc.migration_backups(fresh=True, applied=["008"], daily_ran=False), [])
        self.assertEqual(backup_svc.migration_backups(fresh=False, applied=[], daily_ran=False), [])

    def test_migration_backups_pre_and_post(self):
        names = ["finhub.db-20260811-010000.bak", "finhub.db-20260811-020000.bak"]
        with patch.object(backup_svc, "_filename", side_effect=names):
            created = backup_svc.migration_backups(fresh=False, applied=["009_new"], daily_ran=False)
        self.assertEqual(len(created), 2)
        self.assertEqual([p.name for p in created], names)
        for p in created:
            self.assertTrue(backup_svc.verify_backup(p))

    def test_migration_backups_reuse_daily_as_pre(self):
        created = backup_svc.migration_backups(fresh=False, applied=["009_new"], daily_ran=True)
        self.assertEqual(len(created), 1)

    def test_migration_backups_skip_when_disabled(self):
        with patch.object(backup_svc, "backup_enabled", return_value=False):
            created = backup_svc.migration_backups(fresh=False, applied=["009_new"], daily_ran=False)
        self.assertEqual(created, [])

    # -- restore -------------------------------------------------------------

    def test_restore_from_backup(self):
        backup = backup_svc.create_backup("test")
        self.db.unlink()
        restored = backup_svc.restore_from_backup(backup)
        self.assertEqual(restored, self.db)
        self.assertTrue(backup_svc.verify_backup(self.db))

    def test_restore_refuses_invalid_backup(self):
        junk = self.backup_dir / "junk.bak"
        junk.write_bytes(b"not a database")
        with self.assertRaises(backup_svc.BackupError):
            backup_svc.restore_from_backup(junk)

    # -- config --------------------------------------------------------------

    def test_env_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(backup_svc.backup_enabled())
            self.assertEqual(backup_svc.backup_retention(), 7)
            self.assertEqual(backup_svc.backup_cron(), "03:00")

    def test_env_parsing(self):
        with patch.dict(os.environ, {"BACKUP_ENABLED": "0", "BACKUP_RETENTION": "14", "BACKUP_CRON": "04:30"}):
            self.assertFalse(backup_svc.backup_enabled())
            self.assertEqual(backup_svc.backup_retention(), 14)
            self.assertEqual(backup_svc.backup_cron(), "04:30")


if __name__ == "__main__":
    unittest.main()
