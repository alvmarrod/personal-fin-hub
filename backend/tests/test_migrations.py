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
        self.assertEqual(len(applied), 28)
        self.assertEqual(applied[0], "001_purchase_date")
        self.assertEqual(applied[-1], "028_usa_10y_yield_source")

    def test_bootstrap_is_idempotent(self):
        from db.connection import _run_migrations

        _run_migrations(self.conn)
        _run_migrations(self.conn)
        count = self.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(count, 28)

    def test_run_migrations_reports_applied_versions(self):
        from db.connection import _run_migrations

        applied = _run_migrations(self.conn)
        self.assertEqual(len(applied), 28)
        self.assertEqual(applied[-1], "028_usa_10y_yield_source")

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
        self.assertEqual(len(applied), 28)
        self.assertEqual(applied[-1], "028_usa_10y_yield_source")

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


class TestDropTaxType(unittest.TestCase):
    """Migration 022: backfill NULL tax_definition_id rows onto a generic
    definition, then rebuild transaction_taxes without tax_type (NOT NULL)."""

    MODULE = "db.migrations.022_drop_tax_type"

    def _build(self):
        # End state of 021: tax_definitions present, transaction_taxes still
        # has the free-text tax_type column and a nullable FK.
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tax_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                ruleset_key TEXT,
                name TEXT NOT NULL,
                rate REAL,
                year_start INTEGER
            );
            CREATE TABLE transaction_taxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                tax_definition_id INTEGER,
                tax_type TEXT NOT NULL,
                tax_rate REAL,
                tax_amount REAL,
                currency TEXT NOT NULL,
                profile_id INTEGER
            );
        """)
        conn.commit()
        return conn

    def _seed(self, conn):
        conn.execute("INSERT INTO tax_definitions (slug, ruleset_key, name) VALUES ('other', NULL, 'Other')")
        def_id = conn.execute("SELECT id FROM tax_definitions WHERE slug='other'").fetchone()["id"]
        conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_type, tax_amount, currency) "
            "VALUES (1, NULL, 'WITHHOLDING', 5.0, 'USD')"
        )
        conn.execute(
            "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_type, tax_amount, currency) "
            "VALUES (2, ?, 'STAMP', 3.0, 'USD')",
            (def_id,),
        )
        conn.commit()
        return def_id

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_verify_false_before(self):
        conn = self._build()
        self._seed(conn)
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertFalse(mod.verify(conn))
        conn.close()

    def test_backfills_legacy_row_and_drops_column(self):
        conn = self._build()
        self._seed(conn)

        mod = self._apply(conn)
        self.assertTrue(mod.verify(conn))
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(transaction_taxes)").fetchall()]
        self.assertNotIn("tax_type", cols)
        self.assertIn("tax_definition_id", cols)

        rows = conn.execute("SELECT id, tax_definition_id FROM transaction_taxes ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        gen = conn.execute("SELECT id FROM tax_definitions WHERE slug='foreign_withholding'").fetchone()["id"]
        other = conn.execute("SELECT id FROM tax_definitions WHERE slug='other'").fetchone()["id"]
        self.assertEqual(
            rows[0]["tax_definition_id"],
            gen,
            "legacy NULL-FK row must be backfilled onto the generic definition",
        )
        self.assertEqual(rows[1]["tax_definition_id"], other, "definition-linked row must keep its definition")

        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO transaction_taxes (transaction_id, tax_definition_id, tax_amount, currency) "
                "VALUES (3, NULL, 1.0, 'USD')"
            )

        idx = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        self.assertIn("idx_transaction_taxes_profile", idx)
        conn.close()

    def test_up_is_idempotent(self):
        conn = self._build()
        self._seed(conn)
        self._apply(conn)
        count = len(conn.execute("SELECT * FROM transaction_taxes").fetchall())
        self._apply(conn)
        self.assertEqual(len(conn.execute("SELECT * FROM transaction_taxes").fetchall()), count)
        self.assertEqual(
            len(conn.execute("SELECT id FROM tax_definitions WHERE slug='foreign_withholding'").fetchall()),
            1,
        )
        conn.close()

    def test_verify_true_on_clean_schema(self):
        conn = self._build()
        conn.execute("DROP TABLE transaction_taxes")
        conn.execute("""
            CREATE TABLE transaction_taxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                tax_definition_id INTEGER NOT NULL,
                tax_rate REAL,
                tax_amount REAL,
                currency TEXT NOT NULL,
                profile_id INTEGER
            )
        """)
        conn.commit()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertTrue(mod.verify(conn))
        conn.close()


class TestSeedTaxCatalog(unittest.TestCase):
    """Migration 023: seed the real Spain/Japan/default tax catalog, Tasa
    Tobin, the generic foreign_withholding definition, and the broker fees."""

    MODULE = "db.migrations.023_seed_tax_catalog"

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        return conn

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_verify_false_before(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertFalse(mod.verify(conn))
        conn.close()

    def test_verify_true_after(self):
        conn = self._build()
        mod = self._apply(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_seeds_bases_categories_and_brackets(self):
        conn = self._build()
        self._apply(conn)

        bases = {r["ruleset_key"]: r for r in conn.execute("SELECT * FROM tax_bases").fetchall()}
        self.assertEqual(set(bases), {"spain", "default", "japan"})

        self.assertEqual(bases["spain"]["name"], "IRPF sobre el ahorro")
        self.assertEqual(bases["spain"]["computation"], "progressive")
        self.assertEqual(bases["default"]["name"], "IRPF sobre el ahorro")
        self.assertEqual(bases["default"]["computation"], "progressive")
        self.assertEqual(bases["japan"]["name"], "Impuesto de capitales")
        self.assertEqual(bases["japan"]["computation"], "flat")
        self.assertAlmostEqual(bases["japan"]["flat_rate"], 0.20315, places=5)

        for ruleset in ("spain", "default", "japan"):
            cats = {
                r["category"]
                for r in conn.execute(
                    "SELECT category FROM tax_base_categories WHERE tax_base_id = ?",
                    (bases[ruleset]["id"],),
                ).fetchall()
            }
            self.assertEqual(cats, {"capital_gains", "dividends", "interest"})

        for ruleset in ("spain", "default"):
            rows = conn.execute(
                "SELECT from_amount, to_amount, rate FROM tax_base_rates WHERE tax_base_id = ? ORDER BY from_amount",
                (bases[ruleset]["id"],),
            ).fetchall()
            self.assertEqual(len(rows), 5)
            self.assertEqual(
                [(r["from_amount"], r["to_amount"], r["rate"]) for r in rows],
                [
                    (0, 6000, 0.19),
                    (6000, 50000, 0.21),
                    (50000, 200000, 0.23),
                    (200000, 300000, 0.27),
                    (300000, None, 0.30),
                ],
            )

        # No base for latest/none — they stay base-less by design.
        self.assertIsNone(conn.execute("SELECT 1 FROM tax_bases WHERE ruleset_key IN ('latest', 'none')").fetchone())
        conn.close()

    def test_seeds_definitions(self):
        conn = self._build()
        self._apply(conn)

        tobin = conn.execute("SELECT * FROM tax_definitions WHERE slug = 'spain_itf'").fetchone()
        self.assertIsNotNone(tobin)
        self.assertEqual(tobin["ruleset_key"], "spain")
        self.assertEqual(tobin["name"], "Tasa Tobin")
        self.assertAlmostEqual(tobin["rate"], 0.002, places=4)

        generic = conn.execute("SELECT * FROM tax_definitions WHERE slug = 'foreign_withholding'").fetchone()
        self.assertIsNotNone(generic)
        self.assertIsNone(generic["ruleset_key"])
        self.assertIsNone(generic["rate"])
        conn.close()

    def test_seeds_broker_fees(self):
        conn = self._build()
        self._apply(conn)
        names = {r["name"] for r in conn.execute("SELECT name FROM broker_fee_definitions").fetchall()}
        self.assertEqual(names, {"Fee de compra", "Fee de venta", "Fee de cambio de divisa (FX)"})
        conn.close()

    def test_up_is_idempotent(self):
        conn = self._build()
        mod = self._apply(conn)
        counts = {
            "bases": conn.execute("SELECT COUNT(*) FROM tax_bases").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM tax_base_categories").fetchone()[0],
            "rates": conn.execute("SELECT COUNT(*) FROM tax_base_rates").fetchone()[0],
            "definitions": conn.execute("SELECT COUNT(*) FROM tax_definitions").fetchone()[0],
            "fees": conn.execute("SELECT COUNT(*) FROM broker_fee_definitions").fetchone()[0],
        }
        self.assertEqual(counts, {"bases": 3, "categories": 9, "rates": 10, "definitions": 2, "fees": 3})

        mod.up(conn)
        again = {
            "bases": conn.execute("SELECT COUNT(*) FROM tax_bases").fetchone()[0],
            "categories": conn.execute("SELECT COUNT(*) FROM tax_base_categories").fetchone()[0],
            "rates": conn.execute("SELECT COUNT(*) FROM tax_base_rates").fetchone()[0],
            "definitions": conn.execute("SELECT COUNT(*) FROM tax_definitions").fetchone()[0],
            "fees": conn.execute("SELECT COUNT(*) FROM broker_fee_definitions").fetchone()[0],
        }
        self.assertEqual(again, counts, "second run must not duplicate any seed row")
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_respects_user_created_base(self):
        conn = self._build()
        conn.execute(
            "INSERT INTO tax_bases (ruleset_key, name, computation, flat_rate, year_start)"
            " VALUES ('spain', 'My custom base', 'progressive', NULL, NULL)"
        )
        conn.commit()
        self._apply(conn)
        rows = conn.execute("SELECT name FROM tax_bases WHERE ruleset_key = 'spain'").fetchall()
        self.assertEqual(len(rows), 1, "a user-created spain base must not be duplicated")
        self.assertEqual(rows[0]["name"], "My custom base")
        conn.close()


class TestMacroSeriesMigration(unittest.TestCase):
    """Migration 024: create the macro source tables and seed the eight
    Wired series from doc/datasources/macro.md (official providers).
    The Reserved Spain CPI row is deliberately not seeded."""

    MODULE = "db.migrations.024_macro_series"
    WIRED = {
        "boj-policy-rate",
        "ecb-deposit-rate",
        "usa-cpi-yoy",
        "japan-cpi-yoy",
        "eurozone-cpi-yoy",
        "usa-m2-money-supply",
        "japan-m2-yoy",
        "eurozone-m2-yoy",
    }

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Start from a schema WITHOUT the macro tables to simulate an old DB.
        schema = SCHEMA_PATH.read_text()
        schema = schema.split("CREATE TABLE macro_series")[0]
        conn.executescript(schema)
        return conn

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_verify_false_before(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertFalse(mod.verify(conn))
        conn.close()

    def test_verify_true_after(self):
        conn = self._build()
        mod = self._apply(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_seeds_all_wired_series(self):
        conn = self._build()
        self._apply(conn)
        slugs = {r["slug"] for r in conn.execute("SELECT slug FROM macro_series").fetchall()}
        self.assertEqual(slugs, self.WIRED)
        conn.close()

    def test_provider_values_are_valid(self):
        conn = self._build()
        self._apply(conn)
        rows = {r["slug"]: r["provider"] for r in conn.execute("SELECT slug, provider FROM macro_series").fetchall()}
        self.assertEqual(rows["eurozone-m2-yoy"], "ecb")
        self.assertEqual(rows["usa-cpi-yoy"], "bls")
        conn.close()

    def test_is_idempotent(self):
        conn = self._build()
        mod = self._apply(conn)
        mod.up(conn)
        count = conn.execute("SELECT COUNT(*) AS c FROM macro_series").fetchone()["c"]
        self.assertEqual(count, len(self.WIRED))
        conn.close()

    def test_observation_unique_constraint(self):
        conn = self._build()
        self._apply(conn)
        conn.execute(
            "INSERT INTO macro_series_observations (slug, obs_date, value) VALUES ('usa-cpi-yoy', '2026-08-01', 3.2)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO macro_series_observations (slug, obs_date, value)"
            " VALUES ('usa-cpi-yoy', '2026-08-01', 9.9)"
        )
        rows = conn.execute("SELECT value FROM macro_series_observations WHERE slug = 'usa-cpi-yoy'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 3.2)
        conn.close()

    def test_respects_user_created_series(self):
        conn = self._build()
        self._apply(conn)
        conn.execute(
            "INSERT OR IGNORE INTO macro_series (slug, provider, name, source_url)"
            " VALUES ('usa-cpi-yoy', 'bls', 'My name', 'x')"
        )
        rows = conn.execute("SELECT name FROM macro_series WHERE slug = 'usa-cpi-yoy'").fetchall()
        self.assertEqual(len(rows), 1)
        conn.close()


class TestEcbDepositRateSourceMigration(unittest.TestCase):
    """Migration 025: repoint ecb-deposit-rate to the ECB data-api SDMX
    endpoint (data-only; no schema change)."""

    MODULE = "db.migrations.025_ecb_deposit_rate_source"

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        return conn

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_updates_provider_and_url(self):
        conn = self._build()
        # Simulate the pre-025 row (investing.com URL).
        conn.execute(
            "INSERT INTO macro_series (slug, provider, name, source_url) "
            "VALUES ('ecb-deposit-rate', 'ecb', 'Eurozone Interest Rate Decision', 'https://x')"
        )
        mod = self._apply(conn)
        row = conn.execute("SELECT provider, source_url FROM macro_series WHERE slug = 'ecb-deposit-rate'").fetchone()
        self.assertEqual(row["provider"], "ecb")
        self.assertIn("data-api.ecb.europa.eu", row["source_url"])
        self.assertIn("FM/D.U2.EUR.4F.KR.DFR.LEV", row["source_url"])
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_verify_false_when_row_missing(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertFalse(mod.verify(conn))
        conn.close()

    def test_idempotent(self):
        conn = self._build()
        conn.execute(
            "INSERT INTO macro_series (slug, provider, name, source_url) "
            "VALUES ('ecb-deposit-rate', 'ecb', 'x', 'https://x')"
        )
        mod = self._apply(conn)
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()


class TestOfficialMacroSourcesMigration(unittest.TestCase):
    """Migration 026: widen the macro provider CHECK, repoint the five
    Investing.com series to official sources, and clear japan-cpi-yoy (no
    datasource yet)."""

    MODULE = "db.migrations.026_official_macro_sources"

    EXPECTED = {
        "boj-policy-rate": "boj",
        "usa-cpi-yoy": "bls",
        "eurozone-cpi-yoy": "eurostat",
        "usa-m2-money-supply": "fred",
        "japan-m2-yoy": "boj",
    }

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        # Recreate macro_series with the pre-026 CHECK (schema.sql is final
        # state and already has the widened one).
        conn.executescript(
            """
            DROP TABLE IF EXISTS macro_series_observations;
            DROP TABLE IF EXISTS macro_series;
            CREATE TABLE macro_series (
                slug TEXT PRIMARY KEY,
                provider TEXT NOT NULL CHECK (provider IN ('investing-com', 'ecb')),
                name TEXT NOT NULL,
                unit TEXT,
                source_url TEXT NOT NULL,
                update_frequency TEXT,
                last_synced_at DATETIME
            );
            CREATE TABLE macro_series_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL REFERENCES macro_series(slug),
                obs_date DATE NOT NULL,
                value REAL NOT NULL,
                UNIQUE(slug, obs_date)
            );
            """
        )
        # Seed the pre-026 state: old provider values incl. investing-com.
        rows = [
            ("boj-policy-rate", "investing-com"),
            ("ecb-deposit-rate", "ecb"),
            ("eurozone-cpi-yoy", "investing-com"),
            ("eurozone-m2-yoy", "ecb"),
            ("japan-cpi-yoy", "investing-com"),
            ("japan-m2-yoy", "investing-com"),
            ("usa-cpi-yoy", "investing-com"),
            ("usa-m2-money-supply", "investing-com"),
        ]
        for slug, provider in rows:
            conn.execute(
                "INSERT INTO macro_series (slug, provider, name, source_url) VALUES (?, ?, ?, ?)",
                (slug, provider, slug, "https://old"),
            )
        conn.commit()
        return conn

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_repoints_five_series(self):
        conn = self._build()
        mod = self._apply(conn)
        got = {r["slug"]: r["provider"] for r in conn.execute("SELECT slug, provider FROM macro_series").fetchall()}
        for slug, provider in self.EXPECTED.items():
            self.assertEqual(got[slug], provider)
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_clears_japan_cpi(self):
        conn = self._build()
        self._apply(conn)
        row = conn.execute("SELECT provider, source_url FROM macro_series WHERE slug = 'japan-cpi-yoy'").fetchone()
        self.assertIsNone(row["provider"])
        self.assertIsNone(row["source_url"])
        conn.close()

    def test_check_rejects_investing_com(self):
        conn = self._build()
        self._apply(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO macro_series (slug, provider, name) VALUES ('x', 'investing-com', 'x')")
        conn.close()

    def test_check_accepts_new_providers(self):
        conn = self._build()
        self._apply(conn)
        for provider in ("boj", "bls", "eurostat", "fred", "ecb"):
            conn.execute(
                "INSERT INTO macro_series (slug, provider, name) VALUES (?, ?, 'x')",
                (f"s-{provider}", provider),
            )
        conn.close()

    def test_preserves_observations(self):
        conn = self._build()
        conn.execute(
            "INSERT INTO macro_series_observations (slug, obs_date, value) VALUES ('usa-cpi-yoy', '2025-01-01', 1.0)"
        )
        conn.commit()
        self._apply(conn)
        n = conn.execute("SELECT COUNT(*) AS c FROM macro_series_observations").fetchone()["c"]
        self.assertEqual(n, 1)
        conn.close()

    def test_idempotent(self):
        conn = self._build()
        mod = self._apply(conn)
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()

    def test_verify_false_before(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        self.assertFalse(mod.verify(conn))
        conn.close()


class TestUsaPolicyRateSourceMigration(unittest.TestCase):
    """Migration 027: widen the provider CHECK to allow `market-api` and seed
    the `usa-13w-bill-rate` series (the ^IRX policy-rate proxy)."""

    MODULE = "db.migrations.027_usa_policy_rate_source"
    PRE_CHECK = "provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred')"

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        # Recreate macro_series with the pre-027 CHECK (no market-api).
        conn.executescript(
            """
            DROP TABLE IF EXISTS macro_series_observations;
            DROP TABLE IF EXISTS macro_series;
            CREATE TABLE macro_series (
                slug TEXT PRIMARY KEY,
                provider TEXT CHECK (provider IN ('ecb', 'boj', 'bls', 'eurostat', 'fred')),
                name TEXT NOT NULL,
                unit TEXT,
                source_url TEXT,
                update_frequency TEXT,
                last_synced_at DATETIME
            );
            CREATE TABLE macro_series_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL REFERENCES macro_series(slug),
                obs_date DATE NOT NULL,
                value REAL NOT NULL,
                UNIQUE(slug, obs_date)
            );
            """
        )
        conn.execute("INSERT INTO macro_series (slug, provider, name) VALUES ('usa-cpi-yoy', 'bls', 'CPI')")
        conn.commit()
        return conn

    def _apply(self, conn):
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        return mod

    def test_verify_false_before(self):
        conn = self._build()
        from importlib import import_module

        self.assertFalse(import_module(self.MODULE).verify(conn))
        conn.close()

    def test_seeds_and_verifies(self):
        conn = self._build()
        mod = self._apply(conn)
        self.assertTrue(mod.verify(conn))
        row = conn.execute("SELECT provider, source_url FROM macro_series WHERE slug = 'usa-13w-bill-rate'").fetchone()
        self.assertEqual(row["provider"], "market-api")
        self.assertEqual(row["source_url"], "^IRX")
        conn.close()

    def test_check_accepts_market_api(self):
        conn = self._build()
        self._apply(conn)
        conn.execute("INSERT INTO macro_series (slug, provider, name) VALUES ('x', 'market-api', 'x')")
        conn.close()

    def test_preserves_observations(self):
        conn = self._build()
        conn.execute(
            "INSERT INTO macro_series_observations (slug, obs_date, value) VALUES ('usa-cpi-yoy', '2025-01-01', 1.0)"
        )
        conn.commit()
        self._apply(conn)
        n = conn.execute("SELECT COUNT(*) AS c FROM macro_series_observations").fetchone()["c"]
        self.assertEqual(n, 1)
        conn.close()

    def test_idempotent(self):
        conn = self._build()
        mod = self._apply(conn)
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        conn.close()


class TestUsa10yYieldSourceMigration(unittest.TestCase):
    """Migration 028: seed `usa-10y-treasury-yield` (^TNX), data-only."""

    MODULE = "db.migrations.028_usa_10y_yield_source"

    def _build(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_PATH.read_text())
        return conn

    def test_verify_false_before(self):
        conn = self._build()
        from importlib import import_module

        self.assertFalse(import_module(self.MODULE).verify(conn))
        conn.close()

    def test_seeds_and_verifies(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        self.assertTrue(mod.verify(conn))
        row = conn.execute(
            "SELECT provider, source_url FROM macro_series WHERE slug = 'usa-10y-treasury-yield'"
        ).fetchone()
        self.assertEqual(row["provider"], "market-api")
        self.assertEqual(row["source_url"], "^TNX")
        conn.close()

    def test_idempotent(self):
        conn = self._build()
        from importlib import import_module

        mod = import_module(self.MODULE)
        mod.up(conn)
        mod.up(conn)
        n = conn.execute("SELECT COUNT(*) AS c FROM macro_series WHERE slug = 'usa-10y-treasury-yield'").fetchone()["c"]
        self.assertEqual(n, 1)
        conn.close()
