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
        self.assertEqual(len(applied), 20)
        self.assertEqual(applied[0], "001_purchase_date")
        self.assertEqual(applied[-1], "020_backfill_jst_to_utc")

    def test_bootstrap_is_idempotent(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        _run_migrations(self.conn)
        count = self.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(count, 20)

    def test_run_migrations_reports_applied_versions(self):
        from db.connection import _run_migrations

        applied = _run_migrations(self.conn)
        self.assertEqual(len(applied), 20)
        self.assertEqual(applied[-1], "020_backfill_jst_to_utc")

        applied_again = _run_migrations(self.conn)
        self.assertEqual(applied_again, [])

    def test_only_unapplied_run(self):
        from db.connection import _run_migrations

        # Mark first 7 as applied, last 13 pending
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
        self.assertEqual(len(applied), 20)
        self.assertEqual(applied[-1], "020_backfill_jst_to_utc")

    def test_020_converts_mixed_rows_during_bootstrap(self):
        from db.connection import _run_migrations

        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Bank', 'BANK')")
        self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) "
            "VALUES ('2026-08-01T00:00:00', 'INCOME', 1, 'USD', 100), "
            "('2026-08-01T05:30:00.123456+00:00', 'INCOME', 1, 'USD', 50)"
        )
        naive_id, aware_id = (r["id"] for r in self.conn.execute("SELECT id FROM transactions ORDER BY id").fetchall())
        self.conn.execute(
            "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp) "
            "VALUES (1, 'USD', 100, '2026-08-01T00:00:00')"
        )
        self.conn.commit()

        applied = _run_migrations(self.conn)
        self.assertIn("020_backfill_jst_to_utc", applied)

        rows = self.conn.execute("SELECT id, timestamp FROM transactions").fetchall()
        by_id = {r["id"]: r["timestamp"] for r in rows}
        self.assertEqual(by_id[naive_id], "2026-07-31T15:00:00")
        self.assertEqual(by_id[aware_id], "2026-08-01T05:30:00")

        snap_ts = self.conn.execute("SELECT timestamp FROM balance_snapshots").fetchone()["timestamp"]
        self.assertEqual(snap_ts, "2026-07-31T15:00:00")

        self.assertEqual(_run_migrations(self.conn), [])

    def test_020_unapplied_naive_only_db_still_converts(self):
        # A pre-model DB with no offset-suffixed rows (scheduler never fired)
        # must still be converted, even though verify() sees no suffix.
        from db.connection import _run_migrations

        self.conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Bank', 'BANK')")
        tx_id = self.conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) "
            "VALUES ('2026-08-01T17:30:00', 'INCOME', 1, 'USD', 100)"
        ).lastrowid
        self.conn.commit()

        applied = _run_migrations(self.conn)
        self.assertIn("020_backfill_jst_to_utc", applied)
        self.assertEqual(
            self.conn.execute("SELECT timestamp FROM transactions WHERE id = ?", (tx_id,)).fetchone()["timestamp"],
            "2026-08-01T08:30:00",
        )

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
            "VALUES ('2024-01-01T00:00:00', 'INCOME', 1, 'USD', 1000)"
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


class TestRenameInvestmentCategory(unittest.TestCase):
    """Migration 011 renames transactions.transaction_category to investment_transaction_category."""

    def _build_old_schema(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,
                transaction_category TEXT,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL
            )
        """)
        conn.execute(
            "INSERT INTO transactions (timestamp, type, transaction_category, entity_id, currency, total_value) "
            "VALUES ('2024-01-01T00:00:00', 'INVESTMENT_BUY', 'DCA', 1, 'USD', 100)"
        )
        conn.commit()
        return conn

    def test_up_renames_column_and_preserves_data(self):
        conn = self._build_old_schema()
        from importlib import import_module

        mod = import_module("db.migrations.011_rename_investment_category")
        self.assertFalse(mod.verify(conn))
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
        self.assertIn("investment_transaction_category", cols)
        self.assertNotIn("transaction_category", cols)
        row = conn.execute("SELECT investment_transaction_category FROM transactions").fetchone()
        self.assertEqual(row["investment_transaction_category"], "DCA")
        conn.close()

    def test_up_is_idempotent_on_fresh_schema(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,
                investment_transaction_category TEXT,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL
            )
        """)
        conn.commit()
        from importlib import import_module

        mod = import_module("db.migrations.011_rename_investment_category")
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()


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
        "011_rename_investment_category",
        "012_fiscal_periods",
        "013_tax_rates",
        "014_add_cashback_category",
        "015_balance_snapshot_id",
        "016_consolidate_auto_snapshots",
        "017_persist_cash_handling",
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
            "VALUES ('2024-01-01T00:00:00', 'INCOME', 1, 'USD', 1000)"
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
            "('2024-01-01T00:00:00', 'INCOME', 1, 'USD', 1000), "
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


class TestPersistCashHandling(unittest.TestCase):
    """Migration 017: transactions.cash_handling + balance_adjustment_links."""

    def _build_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL,
                notes TEXT,
                balance_snapshot_id INTEGER
            )
        """)
        return conn

    @staticmethod
    def _insert(conn, ts, tx_type, total_value=100.0, entity_id=1, currency="USD", notes=None, snapshot_id=None):
        cur = conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, notes, balance_snapshot_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, tx_type, entity_id, currency, total_value, notes, snapshot_id),
        )
        return cur.lastrowid

    @staticmethod
    def _links(conn, adj_id=None):
        if adj_id is None:
            return conn.execute("SELECT * FROM balance_adjustment_links ORDER BY id").fetchall()
        return conn.execute(
            "SELECT * FROM balance_adjustment_links WHERE balance_adjustment_id = ?", (adj_id,)
        ).fetchall()

    def test_up_adds_column_and_table(self):
        conn = self._build_conn()
        from importlib import import_module

        mod = import_module("db.migrations.017_persist_cash_handling")
        self.assertFalse(mod.verify(conn))
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
        self.assertIn("cash_handling", cols)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn("balance_adjustment_links", tables)
        # CHECK constraint rejects invalid modes
        self._insert(conn, "2024-01-01T00:00:00", "MONEY_OUT")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE transactions SET cash_handling = 'auto'")
        conn.close()

    def test_backfill_links_next_day_spends(self):
        conn = self._build_conn()
        from importlib import import_module

        inj = self._insert(
            conn, "2024-03-14T23:59:59", "BALANCE_ADJUSTMENT", 500.0, notes="Inferred cash for investment purchases"
        )
        buy = self._insert(conn, "2024-03-15T10:00:00", "INVESTMENT_BUY", 300.0)
        out = self._insert(conn, "2024-03-15T12:00:00", "MONEY_OUT", 200.0)
        other_pair = self._insert(conn, "2024-03-15T10:00:00", "INVESTMENT_BUY", 50.0, entity_id=2, currency="EUR")
        later_spend = self._insert(conn, "2024-03-16T10:00:00", "INVESTMENT_BUY", 75.0)

        mod = import_module("db.migrations.017_persist_cash_handling")
        mod.up(conn)

        linked = {r["linked_transaction_id"] for r in self._links(conn, inj)}
        self.assertEqual(linked, {buy, out})
        all_linked_ids = {r["linked_transaction_id"] for r in self._links(conn)}
        self.assertNotIn(other_pair, all_linked_ids)
        self.assertNotIn(later_spend, all_linked_ids)
        conn.close()

    def test_backfill_skips_snapshot_linked_and_non_injection_adjustments(self):
        conn = self._build_conn()
        from importlib import import_module

        snap_adj = self._insert(
            conn,
            "2024-03-14T23:59:59",
            "BALANCE_ADJUSTMENT",
            500.0,
            notes="Balance adjustment for snapshot at X",
            snapshot_id=7,
        )
        unmarked = self._insert(conn, "2024-03-14T23:59:59", "BALANCE_ADJUSTMENT", 10.0, notes="manual top-up")
        self._insert(conn, "2024-03-15T10:00:00", "INVESTMENT_BUY", 300.0)

        mod = import_module("db.migrations.017_persist_cash_handling")
        mod.up(conn)

        self.assertEqual(len(self._links(conn)), 0)
        self.assertEqual(len(self._links(conn, snap_adj)), 0)
        self.assertEqual(len(self._links(conn, unmarked)), 0)
        conn.close()

    def test_unlinked_injection_still_verifies(self):
        conn = self._build_conn()
        from importlib import import_module

        orphan = self._insert(
            conn, "2024-03-14T23:59:59", "BALANCE_ADJUSTMENT", 500.0, notes="Inferred cash for investment purchases"
        )

        mod = import_module("db.migrations.017_persist_cash_handling")
        mod.up(conn)

        self.assertTrue(mod.verify(conn))
        self.assertEqual(len(self._links(conn, orphan)), 0)
        conn.close()

    def test_up_is_idempotent(self):
        conn = self._build_conn()
        from importlib import import_module

        inj = self._insert(
            conn, "2024-03-14T23:59:59", "BALANCE_ADJUSTMENT", 500.0, notes="Inferred cash for investment purchases"
        )
        buy = self._insert(conn, "2024-03-15T10:00:00", "INVESTMENT_BUY", 300.0)

        mod = import_module("db.migrations.017_persist_cash_handling")
        mod.up(conn)
        mod.up(conn)

        links = self._links(conn, inj)
        self.assertEqual([(r["balance_adjustment_id"], r["linked_transaction_id"]) for r in links], [(inj, buy)])
        conn.close()


class TestBackfillJstToUtc(unittest.TestCase):
    """Migration 020 per-row triage of the two pre-model timestamp populations:

    - naive values are JST wall-clock → shift −9h to UTC;
    - values with an explicit offset are already UTC instants → strip only.
    """

    MODULE = "db.migrations.020_backfill_jst_to_utc"

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE balance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                currency TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE manual_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_asset_id INTEGER NOT NULL,
                value REAL NOT NULL,
                effective_date DATE NOT NULL,
                recorded_at DATETIME NOT NULL DEFAULT (datetime('now')),
                notes TEXT
            )
        """)
        conn.commit()
        return conn

    def _insert_tx(self, conn, ts):
        cur = conn.execute(
            "INSERT INTO transactions (timestamp, type, entity_id, currency, total_value) "
            "VALUES (?, 'INCOME', 1, 'USD', 100)",
            (ts,),
        )
        return cur.lastrowid

    def _tx_ts(self, conn, tx_id):
        return conn.execute("SELECT timestamp FROM transactions WHERE id = ?", (tx_id,)).fetchone()["timestamp"]

    def _apply_initial(self, conn):
        """Bootstrap a pre-model DB through 020 exactly like the runner:
        migrations table present, 020 unrecorded → up() converts, then the
        marker is recorded."""
        conn.execute(
            "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.commit()
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        conn.execute("INSERT INTO schema_migrations (version) VALUES ('020_backfill_jst_to_utc')")
        conn.commit()
        return mod

    def test_verify_false_before_true_after(self):
        conn = self._build()
        self._insert_tx(conn, "2026-08-01T05:30:00+00:00")
        conn.commit()

        mod = self._apply_initial(conn)
        self.assertTrue(mod.verify(conn))
        self.assertEqual(self._tx_ts(conn, 1), "2026-08-01T05:30:00")
        conn.close()

    def test_naive_jst_midnight_shifts(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T00:00:00")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-07-31T15:00:00")
        conn.close()

    def test_user_entered_wall_clock_shifts(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T17:30:00")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-08-01T08:30:00")
        conn.close()

    def test_scheduler_running_fire_keeps_instant(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T05:30:00.123456+00:00")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-08-01T05:30:00")
        conn.close()

    def test_z_suffixed_row_kept(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T05:30:00Z")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-08-01T05:30:00")
        conn.close()

    def test_explicit_positive_offset_keeps_instant(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T00:00:00+09:00")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-07-31T15:00:00")
        conn.close()

    def test_sentinel_23_59_59_shifts(self):
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-06-05T23:59:59")
        conn.commit()
        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-06-05T14:59:59")
        conn.close()

    def test_manual_values_recorded_at_untouched(self):
        conn = self._build()
        conn.execute(
            "INSERT INTO manual_values (portfolio_asset_id, value, effective_date) VALUES (1, 10, '2026-01-01')"
        )
        conn.commit()
        recorded = conn.execute("SELECT recorded_at FROM manual_values").fetchone()["recorded_at"]
        self._apply_initial(conn)
        self.assertEqual(
            conn.execute("SELECT recorded_at FROM manual_values").fetchone()["recorded_at"],
            recorded,
        )
        conn.close()

    def test_recorded_db_skips_on_rerun(self):
        # Once recorded, a re-run must leave even a naive-looking row alone:
        # post-model data is naive UTC and must never be re-shifted.
        conn = self._build()
        tx_id = self._insert_tx(conn, "2026-08-01T00:00:00")
        conn.commit()

        self._apply_initial(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-07-31T15:00:00")

        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        self.assertEqual(self._tx_ts(conn, tx_id), "2026-07-31T15:00:00")
        conn.close()

    def test_verify_ignores_naive_midnight(self):
        # A legit UTC instant can end in T00:00:00; that must not read as
        # "not converted".
        conn = self._build()
        self._insert_tx(conn, "2026-08-01T00:00:00")
        conn.commit()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertTrue(mod.verify(conn))
        conn.close()
