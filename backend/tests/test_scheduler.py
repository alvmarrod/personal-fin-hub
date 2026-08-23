import os
import sqlite3
import unittest
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from db import queries
from db.connection import ProfileScopedConnection
from models.enums import EntityType
from services.config import Config

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def make_shared_conn(profile_id=None, name=None) -> sqlite3.Connection:
    name = name or f"sched_{uuid.uuid4().hex}"
    conn = sqlite3.connect(
        f"file:{name}?mode=memory&cache=shared",
        uri=True,
        factory=ProfileScopedConnection,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.profile_id = profile_id
    return conn


def seed_currency(conn: sqlite3.Connection) -> None:
    queries.create_self_rate(conn, "USD", datetime(2024, 1, 1, 0, 0, 0))


def seed_entity(conn: sqlite3.Connection) -> int:
    return queries.create_entity(conn, "Test Broker", EntityType.BROKER)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMakeTrigger(unittest.TestCase):
    def test_one_off_future(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "ONE_OFF",
                "start_date": date(2099, 1, 1),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, DateTrigger)

    def test_one_off_past(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "ONE_OFF",
                "start_date": date(2020, 1, 1),
                "custom_cron": None,
            }
        )
        self.assertIsNone(trigger)

    def test_daily(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "DAILY",
                "start_date": date(2025, 1, 1),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_weekly(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "WEEKLY",
                "start_date": date(2025, 6, 1),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_monthly(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "MONTHLY",
                "start_date": date(2025, 6, 15),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_quarterly(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "QUARTERLY",
                "start_date": date(2025, 6, 15),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_annually(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "ANNUALLY",
                "start_date": date(2025, 6, 15),
                "custom_cron": None,
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_custom_with_cron(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "CUSTOM",
                "start_date": date(2025, 1, 1),
                "custom_cron": "0 12 * * 1",
            }
        )
        self.assertIsInstance(trigger, CronTrigger)

    def test_custom_without_cron(self):
        from scheduler.scheduler import _make_trigger

        trigger = _make_trigger(
            {
                "id": 1,
                "periodicity_type": "CUSTOM",
                "start_date": date(2025, 1, 1),
                "custom_cron": None,
            }
        )
        self.assertIsNone(trigger)


class TestSyncRemoveSchedule(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.patchers = [
            patch("scheduler.scheduler.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.conn.close()

    def test_sync_adds_job(self):
        sid = queries.create_schedule(
            self.conn,
            "Monthly DCA",
            "2025-01-01",
            "MONTHLY",
        )
        from scheduler.scheduler import get_scheduler, sync_schedule

        sync_schedule(sid)
        sched = get_scheduler()
        job = sched.get_job(f"schedule_{sid}")
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "Monthly DCA")

    def test_sync_nonexistent_schedule(self):
        from scheduler.scheduler import get_scheduler, sync_schedule

        sync_schedule(999)
        sched = get_scheduler()
        self.assertIsNone(sched.get_job("schedule_999"))

    def test_remove_removes_job(self):
        sid = queries.create_schedule(
            self.conn,
            "To Remove",
            "2025-01-01",
            "WEEKLY",
        )
        from scheduler.scheduler import get_scheduler, remove_schedule, sync_schedule

        sync_schedule(sid)
        sched = get_scheduler()
        self.assertIsNotNone(sched.get_job(f"schedule_{sid}"))
        remove_schedule(sid)
        self.assertIsNone(sched.get_job(f"schedule_{sid}"))

    def test_remove_nonexistent(self):
        from scheduler.scheduler import remove_schedule

        remove_schedule(999)


class TestCloneTransaction(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.patchers = [
            patch("scheduler.scheduler.get_db", return_value=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.conn.close()

    def test_clone_basic(self):
        sid = queries.create_schedule(
            self.conn,
            "Monthly DCA",
            "2025-01-01",
            "MONTHLY",
            entity_id=self.eid,
            currency="USD",
            type_="INVESTMENT_BUY",
            total_value=500.0,
        )
        from scheduler.scheduler import _clone_tx

        new_id = _clone_tx(sid)
        self.assertIsNotNone(new_id)
        assert new_id is not None
        tx = queries.get_transaction(self.conn, new_id)
        assert tx is not None
        self.assertEqual(tx["entity_id"], self.eid)
        self.assertEqual(tx["currency"], "USD")
        self.assertEqual(tx["type"], "INVESTMENT_BUY")
        self.assertEqual(tx["investment_transaction_category"], "DCA")
        self.assertEqual(tx["total_value"], 500.0)

    def test_clone_skips_soft_deleted_entity(self):
        sid = queries.create_schedule(
            self.conn,
            "Monthly DCA",
            "2025-01-01",
            "MONTHLY",
            entity_id=self.eid,
        )
        queries.delete_entity(self.conn, self.eid)
        from scheduler.scheduler import _clone_tx

        new_id = _clone_tx(sid)
        self.assertIsNone(new_id)

    def test_clone_skips_when_entity_id_none(self):
        sid = queries.create_schedule(
            self.conn,
            "No Entity",
            "2025-01-01",
            "MONTHLY",
        )
        from scheduler.scheduler import _clone_tx

        new_id = _clone_tx(sid)
        self.assertIsNone(new_id)

    def test_execute_schedule_creates_transaction(self):
        """Scheduler should create transaction when executed"""
        sid = queries.create_schedule(
            self.conn,
            "Test Schedule",
            "2025-01-01",
            "MONTHLY",
            entity_id=self.eid,
            currency="USD",
            type_="INCOME",
            total_value=100.0,
        )

        # Verify no transactions before execution
        tx_before = self.conn.execute("SELECT COUNT(*) FROM transactions WHERE entity_id = ?", (self.eid,)).fetchone()[
            0
        ]
        self.assertEqual(tx_before, 0)

        # Execute schedule
        from scheduler.scheduler import execute_schedule

        execute_schedule(sid)

        # Verify transaction was created
        tx_after = self.conn.execute("SELECT COUNT(*) FROM transactions WHERE entity_id = ?", (self.eid,)).fetchone()[0]
        self.assertEqual(tx_after, 1)

        # Verify transaction details
        tx = self.conn.execute(
            "SELECT * FROM transactions WHERE entity_id = ? ORDER BY id DESC LIMIT 1", (self.eid,)
        ).fetchone()
        self.assertEqual(tx["total_value"], 100.0)
        self.assertEqual(tx["type"], "INCOME")
        self.assertEqual(tx["currency"], "USD")
        self.assertIsNone(tx["investment_transaction_category"])

    def test_execute_schedule_respects_end_date(self):
        """Scheduler should NOT create transaction if end_date has passed"""
        past_end = (date.today() - timedelta(days=1)).isoformat()
        sid = queries.create_schedule(
            self.conn,
            "Expired Schedule",
            "2025-01-01",
            "MONTHLY",
            end_date=past_end,
            entity_id=self.eid,
            currency="USD",
            type_="INCOME",
            total_value=100.0,
        )

        from scheduler.scheduler import execute_schedule

        execute_schedule(sid)

        tx_count = self.conn.execute("SELECT COUNT(*) FROM transactions WHERE entity_id = ?", (self.eid,)).fetchone()[0]
        self.assertEqual(tx_count, 0)


class TestInitScheduler(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        seed_currency(self.conn)
        self.eid = seed_entity(self.conn)
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.patchers: list[Any] = [
            patch("scheduler.scheduler.get_db", return_value=self.conn),
            # init_scheduler also registers a daily backup job; keep the
            # expected job counts schedule-only in these tests.
            patch.dict("os.environ", {"BACKUP_ENABLED": "0"}),
            # The price-sync cron is always registered; pin it off so the
            # schedule-count assertions below stay schedule-only.
            patch.object(Config, "market_api_sync_cron_hours", new_callable=PropertyMock, return_value=[]),
            # Same for the daily FX rate sync cron.
            patch.object(Config, "market_api_rate_sync_hour_utc", new_callable=PropertyMock, return_value=None),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        from scheduler.scheduler import reset_scheduler

        reset_scheduler()
        self.conn.close()

    def test_init_loads_schedules(self):
        queries.create_schedule(self.conn, "S1", "2025-01-01", "MONTHLY")
        queries.create_schedule(self.conn, "S2", "2025-01-01", "WEEKLY")
        from scheduler.scheduler import get_scheduler, init_scheduler

        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 2)

    def test_init_empty(self):
        from scheduler.scheduler import get_scheduler, init_scheduler

        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 0)

    def test_init_registers_daily_backup_job(self):
        from scheduler.scheduler import get_scheduler, init_scheduler

        with patch.dict(os.environ, {"BACKUP_ENABLED": "1", "BACKUP_TIMEZONE": "UTC"}, clear=False):
            init_scheduler()
        sched = get_scheduler()
        job = sched.get_job("backup_daily")
        self.assertIsNotNone(job)
        self.assertIsInstance(job.trigger, CronTrigger)
        self.assertIn("UTC", str(job.trigger.timezone))

    def test_init_skips_past_one_off(self):
        queries.create_schedule(self.conn, "Past", "2020-01-01", "ONE_OFF")
        from scheduler.scheduler import get_scheduler, init_scheduler

        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 0)

    def test_init_registers_price_sync_job(self):
        from scheduler.scheduler import get_scheduler, init_scheduler

        with patch.object(Config, "market_api_sync_cron_hours", new_callable=PropertyMock, return_value=[0, 12]):
            init_scheduler()
        sched = get_scheduler()
        job = sched.get_job("price_sync")
        self.assertIsNotNone(job)
        self.assertIsInstance(job.trigger, CronTrigger)
        self.assertEqual(job.max_instances, 1)

    def test_init_registers_rate_sync_job(self):
        from scheduler.scheduler import get_scheduler, init_scheduler

        with patch.object(Config, "market_api_rate_sync_hour_utc", new_callable=PropertyMock, return_value=1):
            init_scheduler()
        sched = get_scheduler()
        job = sched.get_job("rate_sync")
        self.assertIsNotNone(job)
        self.assertIsInstance(job.trigger, CronTrigger)
        self.assertEqual(job.max_instances, 1)
        self.assertEqual(job.misfire_grace_time, 21600)

    def test_init_skips_rate_sync_job_when_disabled(self):
        from scheduler.scheduler import get_scheduler, init_scheduler

        with patch.object(Config, "market_api_rate_sync_hour_utc", new_callable=PropertyMock, return_value=None):
            init_scheduler()
        sched = get_scheduler()
        self.assertIsNone(sched.get_job("rate_sync"))


class TestSchedulerProfileScoping(unittest.TestCase):
    """Multi-profile scheduler behavior.

    The scheduler runs outside the request context, so its connection starts
    unscoped. Each schedule's generated transaction / schedule_occurrence /
    balance-adjustment rows must carry the schedule's profile_id and stay
    invisible to other profiles.
    """

    def setUp(self):
        from scheduler.scheduler import reset_scheduler

        self.db_name = f"sched_{uuid.uuid4().hex}"
        self.global_conn = make_shared_conn(name=self.db_name)
        self.global_conn.executescript(SCHEMA_PATH.read_text())
        self.profile_a = queries.create_profile(self.global_conn, "SchedAlpha", None)
        self.profile_b = queries.create_profile(self.global_conn, "SchedBeta", None)
        seed_currency(self.global_conn)
        self.global_conn.commit()
        self.conn_a = make_shared_conn(self.profile_a, name=self.db_name)
        self.conn_b = make_shared_conn(self.profile_b, name=self.db_name)
        self.eid_a = seed_entity(self.conn_a)
        self.eid_b = seed_entity(self.conn_b)
        self.conn_a.commit()
        self.conn_b.commit()
        reset_scheduler()
        self.patchers = [
            patch(
                "scheduler.scheduler.get_db",
                side_effect=lambda: make_shared_conn(name=self.db_name),
            ),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        from scheduler.scheduler import reset_scheduler

        for p in self.patchers:
            p.stop()
        reset_scheduler()
        self.global_conn.close()
        self.conn_a.close()
        self.conn_b.close()

    def _schedule(
        self,
        conn: sqlite3.Connection,
        eid: int,
        start: str,
        total_value: float = 100.0,
        periodicity: str = "DAILY",
    ) -> int:
        return queries.create_schedule(
            conn,
            "Past DCA",
            start,
            periodicity,
            entity_id=eid,
            currency="USD",
            type_="INCOME",
            total_value=total_value,
        )

    def test_clone_stamps_schedule_profile(self):
        from scheduler.scheduler import _clone_tx

        sid = self._schedule(self.conn_a, self.eid_a, "2025-01-01")
        tx_id = _clone_tx(sid)
        self.assertIsNotNone(tx_id)
        assert tx_id is not None
        row = self.global_conn.execute(
            "SELECT profile_id, entity_id FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        self.assertEqual(row["profile_id"], self.profile_a)
        self.assertEqual(row["entity_id"], self.eid_a)
        occ = self.global_conn.execute(
            "SELECT profile_id FROM schedule_occurrences WHERE schedule_id = ?", (sid,)
        ).fetchone()
        self.assertEqual(occ["profile_id"], self.profile_a)

    def test_clone_cross_profile_invisible(self):
        from scheduler.scheduler import _clone_tx

        sid = self._schedule(self.conn_a, self.eid_a, "2025-01-01")
        tx_id = _clone_tx(sid)
        self.assertIsNotNone(tx_id)
        assert tx_id is not None
        txs_b = queries.get_all_transactions(self.conn_b)
        self.assertEqual([t for t in txs_b if t["entity_id"] == self.eid_a], [])
        txs_a = queries.get_all_transactions(self.conn_a)
        self.assertEqual([t["id"] for t in txs_a if t["entity_id"] == self.eid_a], [tx_id])

    def test_execute_schedule_stamps_profile(self):
        from scheduler.scheduler import execute_schedule

        sid = self._schedule(self.conn_b, self.eid_b, "2025-01-01")
        execute_schedule(sid)
        row = self.global_conn.execute(
            "SELECT profile_id FROM transactions WHERE entity_id = ?", (self.eid_b,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["profile_id"], self.profile_b)

    def test_catch_up_single_schedule_stamps_profile(self):
        from scheduler.scheduler import catch_up_single_schedule

        start = (date.today() - timedelta(days=3)).isoformat()
        sid = self._schedule(self.conn_a, self.eid_a, start)
        catch_up_single_schedule(sid)
        rows = self.global_conn.execute(
            "SELECT profile_id, investment_transaction_category FROM transactions WHERE entity_id = ?",
            (self.eid_a,),
        ).fetchall()
        self.assertGreaterEqual(len(rows), 1)
        for r in rows:
            self.assertEqual(r["profile_id"], self.profile_a)
            self.assertIsNone(r["investment_transaction_category"])
        occs = self.global_conn.execute(
            "SELECT profile_id FROM schedule_occurrences WHERE schedule_id = ?", (sid,)
        ).fetchall()
        self.assertGreaterEqual(len(occs), 1)
        for r in occs:
            self.assertEqual(r["profile_id"], self.profile_a)

    def test_catch_up_missed_fires_all_profiles(self):
        from scheduler.scheduler import _set_state, catch_up_missed_fires

        _set_state(
            self.global_conn,
            "last_shutdown_at",
            (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        )
        start_a = (date.today() - timedelta(days=2)).isoformat()
        start_b = (date.today() - timedelta(days=1)).isoformat()
        sid_a = self._schedule(self.conn_a, self.eid_a, start_a, total_value=100.0, periodicity="ONE_OFF")
        sid_b = self._schedule(self.conn_b, self.eid_b, start_b, total_value=200.0, periodicity="ONE_OFF")

        catch_up_missed_fires()

        rows_a = self.global_conn.execute(
            "SELECT profile_id FROM transactions WHERE entity_id = ?", (self.eid_a,)
        ).fetchall()
        self.assertEqual(len(rows_a), 1)
        self.assertEqual(rows_a[0]["profile_id"], self.profile_a)
        rows_b = self.global_conn.execute(
            "SELECT profile_id FROM transactions WHERE entity_id = ?", (self.eid_b,)
        ).fetchall()
        self.assertEqual(len(rows_b), 1)
        self.assertEqual(rows_b[0]["profile_id"], self.profile_b)

        occ_a = self.global_conn.execute(
            "SELECT profile_id FROM schedule_occurrences WHERE schedule_id = ?", (sid_a,)
        ).fetchone()
        self.assertEqual(occ_a["profile_id"], self.profile_a)
        occ_b = self.global_conn.execute(
            "SELECT profile_id FROM schedule_occurrences WHERE schedule_id = ?", (sid_b,)
        ).fetchone()
        self.assertEqual(occ_b["profile_id"], self.profile_b)

    def test_catch_up_missed_fires_idempotent(self):
        from scheduler.scheduler import _set_state, catch_up_missed_fires

        _set_state(
            self.global_conn,
            "last_shutdown_at",
            (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        )
        start_a = (date.today() - timedelta(days=2)).isoformat()
        self._schedule(self.conn_a, self.eid_a, start_a, periodicity="ONE_OFF")

        catch_up_missed_fires()
        first = self.global_conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE entity_id = ?", (self.eid_a,)
        ).fetchone()[0]
        self.assertEqual(first, 1)
        catch_up_missed_fires()
        second = self.global_conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE entity_id = ?", (self.eid_a,)
        ).fetchone()[0]
        self.assertEqual(second, first)

    def test_catch_up_cross_profile_invisible(self):
        from scheduler.scheduler import _set_state, catch_up_missed_fires

        _set_state(
            self.global_conn,
            "last_shutdown_at",
            (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        )
        start_a = (date.today() - timedelta(days=2)).isoformat()
        self._schedule(self.conn_a, self.eid_a, start_a, periodicity="ONE_OFF")

        catch_up_missed_fires()

        txs_a = queries.get_all_transactions(self.conn_a)
        self.assertEqual([t["entity_id"] for t in txs_a], [self.eid_a])
        txs_b = queries.get_all_transactions(self.conn_b)
        self.assertEqual([t["entity_id"] for t in txs_b], [])


if __name__ == "__main__":
    unittest.main()
