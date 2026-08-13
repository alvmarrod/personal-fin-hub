import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(len(applied), 10)
        self.assertEqual(applied[0], "001_purchase_date")
        self.assertEqual(applied[-1], "010_income_category")

    def test_bootstrap_is_idempotent(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        _run_migrations(self.conn)
        count = self.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(count, 10)

    def test_run_migrations_reports_applied_versions(self):
        from db.connection import _run_migrations

        applied = _run_migrations(self.conn)
        self.assertEqual(len(applied), 10)
        self.assertEqual(applied[-1], "010_income_category")

        applied_again = _run_migrations(self.conn)
        self.assertEqual(applied_again, [])

    def test_only_unapplied_run(self):
        from db.connection import _run_migrations

        # Mark first 7 as applied, last 2 pending
        self.conn.execute("DELETE FROM schema_migrations")
        for v in [
            "001_purchase_date",
            "002_backfill_snapshots",
            "003_stock_splits",
            "004_schedule_asset",
            "005_manual_values",
            "006_transfer_types",
            "007_schedule_occurrences",
        ]:
            self.conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (v,))
        self.conn.commit()

        _run_migrations(self.conn)

        applied = [r[0] for r in self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        self.assertEqual(len(applied), 10)
        self.assertEqual(applied[-1], "010_income_category")

    def test_verify_missing_raises(self):
        from tests.migration_helpers import run_with_temp_migration

        with self.assertRaisesRegex(RuntimeError, "must define verify"):
            run_with_temp_migration(self.conn, "999_test_no_verify", "def up(conn):\n    pass\n")

    def test_end_state_not_reached_raises(self):
        from tests.migration_helpers import run_with_temp_migration

        with self.assertRaisesRegex(RuntimeError, "verified end-state"):
            run_with_temp_migration(
                self.conn,
                "999_test_bad_verify",
                "def up(conn):\n    pass\n\ndef verify(conn):\n    return False\n",
            )


class TestLegacyDBMigration(unittest.TestCase):
    """Legacy DB with pre-migration tables but empty schema_migrations."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL
            )
        """)
        self.conn.execute("""
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                start_date DATE NOT NULL,
                periodicity_type TEXT NOT NULL
            )
        """)
        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Broker A', 'BROKER')")
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) "
            "VALUES ('2024-01-01T00:00:00', 'MONEY_IN', 1, 'USD', 1000)"
        )
        self.conn.execute(
            "INSERT INTO schedules (description, start_date, periodicity_type) "
            "VALUES ('Salary', '2024-01-01', 'MONTHLY')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_runs_migrations_on_legacy_db(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)

        applied = [r[0] for r in self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        self.assertTrue(len(applied) >= 8, f"Expected at least 8 migrations, got {len(applied)}: {applied}")

        # Migration 008 must have run: profiles table exists with Default row
        rows = self.conn.execute("SELECT * FROM profiles").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Default")

        # profile_id column must exist on ownership tables with backfill
        for table in ["entities", "transactions", "schedules"]:
            cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            self.assertIn("profile_id", cols, f"{table} missing profile_id")
            nulls = self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE profile_id IS NULL").fetchone()[0]
            self.assertEqual(nulls, 0, f"{table} has unset profile_id values")


class TestContaminatedDB(unittest.TestCase):
    """Reproduces the bad-bootstrap state: schema_migrations claims every
    migration applied (008 included) but no ownership table has profile_id.
    The verification-based runner must re-apply and repair on next boot."""

    MIGRATION_VERSIONS = [
        "001_purchase_date",
        "002_backfill_snapshots",
        "003_stock_splits",
        "004_schedule_asset",
        "005_manual_values",
        "006_transfer_types",
        "007_schedule_occurrences",
        "008_profiles",
        "009_market_asset_last_synced",
        "010_income_category",
    ]

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        # Legacy ownership tables (pre-profile schema)
        self.conn.execute(
            "CREATE TABLE entities (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, entity_type TEXT NOT NULL)"
        )
        self.conn.execute(
            "CREATE TABLE transactions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME NOT NULL, type TEXT NOT NULL, "
            "entity_id INTEGER NOT NULL, currency TEXT NOT NULL, total_value REAL)"
        )
        self.conn.execute(
            "CREATE TABLE schedules ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT NOT NULL, start_date DATE NOT NULL, "
            "periodicity_type TEXT NOT NULL)"
        )
        # Masking artifact: profiles table + Default row created by the old
        # seed_default_profile, which ran independently of any migration.
        self.conn.execute(
            "CREATE TABLE profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, "
            "password_hash TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), "
            "updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        self.conn.execute("INSERT INTO profiles (name, password_hash) VALUES ('Default', NULL)")
        # Bad bootstrap: every migration recorded as applied, none actually applied.
        self.conn.execute(
            "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        for v in self.MIGRATION_VERSIONS:
            self.conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (v,))
        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Broker A', 'BROKER')")
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) "
            "VALUES ('2024-01-01T00:00:00', 'MONEY_IN', 1, 'USD', 1000)"
        )
        self.conn.execute(
            "INSERT INTO schedules (description, start_date, periodicity_type) "
            "VALUES ('Salary', '2024-01-01', 'MONTHLY')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_repairs_recorded_but_not_applied(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)

        default_id = self.conn.execute("SELECT id FROM profiles ORDER BY id ASC LIMIT 1").fetchone()["id"]
        for table in ["entities", "transactions", "schedules"]:
            cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            self.assertIn("profile_id", cols, f"{table} missing profile_id")
            values = {r[0] for r in self.conn.execute(f"SELECT profile_id FROM {table}").fetchall()}
            self.assertEqual(values, {default_id}, f"{table} not backfilled to default profile")

    def test_single_default_profile_preserved(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], 1)


class TestMigrateProfiles(unittest.TestCase):
    """008_profiles migration against a pre-profile (legacy) database."""

    LEGACY_TABLES = [
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            country TEXT,
            description TEXT,
            deleted_at DATETIME DEFAULT NULL
        )
        """,
        """
        CREATE TABLE fiscal_exemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exemption_type TEXT NOT NULL,
            description TEXT,
            exemption_amount REAL DEFAULT 0,
            exemption_rate REAL DEFAULT 100,
            exemption_rate_limit REAL
        )
        """,
        """
        CREATE TABLE portfolio_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_code TEXT NOT NULL,
            distribution_type TEXT,
            dca_status TEXT,
            layer TEXT,
            tactic BOOLEAN DEFAULT FALSE,
            desired_weight REAL,
            ter REAL,
            tracking_mode TEXT DEFAULT 'auto',
            current_value_manual REAL,
            is_active BOOLEAN DEFAULT TRUE,
            closing_date DATE,
            notes TEXT
        )
        """,
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            total_value REAL,
            notes TEXT
        )
        """,
        """
        CREATE TABLE transaction_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            fee_type TEXT NOT NULL,
            nature TEXT NOT NULL,
            fixed_amount REAL DEFAULT 0.0,
            percentage REAL DEFAULT 0.0,
            currency TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE transaction_taxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            tax_type TEXT NOT NULL,
            tax_rate REAL,
            tax_amount REAL,
            currency TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE balance_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME NOT NULL,
            notes TEXT
        )
        """,
        """
        CREATE TABLE schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            periodicity_type TEXT NOT NULL,
            custom_cron TEXT,
            entity_id INTEGER,
            currency TEXT,
            type TEXT,
            total_value REAL,
            notes TEXT,
            portfolio_asset_id INTEGER
        )
        """,
        """
        CREATE TABLE schedule_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            occurrence_date TEXT NOT NULL,
            transaction_id INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE manual_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_asset_id INTEGER NOT NULL,
            value REAL NOT NULL,
            effective_date DATE NOT NULL,
            recorded_at DATETIME NOT NULL DEFAULT (datetime('now')),
            notes TEXT
        )
        """,
    ]

    SHARED_TABLES = [
        """
        CREATE TABLE currencies (
            code TEXT NOT NULL,
            base_code TEXT NOT NULL,
            rate REAL NOT NULL,
            timestamp DATETIME NOT NULL,
            PRIMARY KEY (code, base_code, timestamp)
        )
        """,
        """
        CREATE TABLE market_assets (
            market_code TEXT PRIMARY KEY,
            ticker TEXT,
            asset_type TEXT NOT NULL,
            currency_code TEXT,
            name TEXT,
            exchange TEXT
        )
        """,
        """
        CREATE TABLE prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_code TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            price REAL NOT NULL,
            provider TEXT,
            UNIQUE(market_code, timestamp)
        )
        """,
    ]

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        for ddl in self.LEGACY_TABLES + self.SHARED_TABLES:
            self.conn.execute(ddl)
        self._seed_rows()

    def tearDown(self):
        self.conn.close()

    def _seed_rows(self):
        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Broker A', 'BROKER'), ('Bank B', 'BANK')")
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) VALUES "
            "('2024-01-01T00:00:00', 'MONEY_IN', 1, 'USD', 1000), "
            "('2024-01-02T00:00:00', 'MONEY_OUT', 2, 'EUR', 200)"
        )
        self.conn.execute(
            "INSERT INTO transaction_fees (transaction_id, fee_type, nature, currency) VALUES "
            "(1, 'BROKER', 'FIXED', 'USD')"
        )
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) VALUES "
            "(1, 'USD', 500, '2024-01-01T00:00:00')"
        )
        self.conn.execute(
            "INSERT INTO schedules (description, start_date, periodicity_type) VALUES "
            "('Salary', '2024-01-01', 'MONTHLY')"
        )
        self.conn.execute(
            "INSERT INTO schedule_occurrences (schedule_id, occurrence_date, transaction_id) VALUES "
            "(1, '2024-01-01', 1)"
        )
        self.conn.execute(
            "INSERT INTO manual_values (portfolio_asset_id, value, effective_date) VALUES (1, 100, '2024-01-01')"
        )
        self.conn.execute("INSERT INTO fiscal_exemptions (exemption_type) VALUES ('COUNTRY')")
        self.conn.execute("INSERT INTO portfolio_assets (market_code) VALUES ('AAPL')")
        self.conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_type, currency) VALUES (1, 'WITHHOLDING', 'USD')"
        )
        self.conn.execute(
            "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('USD', 'USD', 1.0, '2024-01-01T00:00:00')"
        )
        self.conn.execute("INSERT INTO market_assets (market_code, asset_type) VALUES ('AAPL', 'STOCK')")
        self.conn.commit()

    def test_creates_default_profile_and_backfills(self):
        from db.connection import _migrate_profiles

        _migrate_profiles(self.conn)

        rows = self.conn.execute("SELECT * FROM profiles").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Default")
        self.assertIsNone(rows[0]["password_hash"])
        default_id = rows[0]["id"]

        for table in [
            "entities",
            "transactions",
            "transaction_fees",
            "transaction_taxes",
            "portfolio_assets",
            "balance_snapshots",
            "schedules",
            "schedule_occurrences",
            "manual_values",
            "fiscal_exemptions",
        ]:
            cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            self.assertIn("profile_id", cols, f"{table} missing profile_id")
            values = {r[0] for r in self.conn.execute(f"SELECT profile_id FROM {table}").fetchall()}
            self.assertEqual(values, {default_id}, f"{table} not fully backfilled")

    def test_shared_tables_untouched(self):
        from db.connection import _migrate_profiles

        _migrate_profiles(self.conn)

        for table in ["currencies", "market_assets", "prices"]:
            cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            self.assertNotIn("profile_id", cols, f"{table} must stay shared")

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM market_assets").fetchone()[0], 1)

    def test_idempotent(self):
        from db.connection import _migrate_profiles

        _migrate_profiles(self.conn)
        _migrate_profiles(self.conn)

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0], 2)

    def test_existing_profile_not_duplicated(self):
        from db.connection import _migrate_profiles

        self.conn.execute(
            "CREATE TABLE profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, password_hash TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        self.conn.execute("INSERT INTO profiles (name, password_hash) VALUES ('Default', NULL)")
        self.conn.commit()

        _migrate_profiles(self.conn)

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], 1)


class TestSeedDefaultProfile(unittest.TestCase):
    """Startup seeding (main.seed_default_profile) on a fresh schema database."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "finhub.db"
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        conn.close()
        self.dir_patcher = patch("db.connection.DB_DIR", self.db_path.parent)
        self.path_patcher = patch("db.connection.DB_PATH", self.db_path)
        self.dir_patcher.start()
        self.path_patcher.start()

    def tearDown(self):
        self.dir_patcher.stop()
        self.path_patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_seed_creates_default_profile(self):
        from main import seed_default_profile

        seed_default_profile()

        conn = self._open()
        try:
            rows = conn.execute("SELECT * FROM profiles").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Default")
            self.assertIsNone(rows[0]["password_hash"])
        finally:
            conn.close()

    def test_seed_is_idempotent(self):
        from main import seed_default_profile

        seed_default_profile()
        seed_default_profile()

        conn = self._open()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0], 1)
        finally:
            conn.close()
