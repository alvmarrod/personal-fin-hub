import sqlite3
import unittest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


class TestMigrationRunner(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_PATH.read_text())

    def tearDown(self):
        self.conn.close()

    def test_bootstrap_marks_all_as_applied(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        applied = [r[0] for r in self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        self.assertEqual(len(applied), 7)
        self.assertEqual(applied[0], "001_purchase_date")
        self.assertEqual(applied[-1], "007_schedule_occurrences")

    def test_bootstrap_is_idempotent(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        _run_migrations(self.conn)
        count = self.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(count, 7)

    def test_only_unapplied_run(self):
        from db.connection import _run_migrations

        # Mark first 5 as applied, last 2 pending
        self.conn.execute("DELETE FROM schema_migrations")
        for v in [
            "001_purchase_date",
            "002_backfill_snapshots",
            "003_stock_splits",
            "004_schedule_asset",
            "005_manual_values",
        ]:
            self.conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (v,))
        self.conn.commit()

        _run_migrations(self.conn)

        applied = [r[0] for r in self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        self.assertEqual(len(applied), 7)
        self.assertEqual(applied[-1], "007_schedule_occurrences")
