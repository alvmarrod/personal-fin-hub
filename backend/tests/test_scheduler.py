import sqlite3
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from db import queries
from models.enums import EntityType

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_currency(conn: sqlite3.Connection) -> None:
    queries.insert_rate(conn, "USD", "USD", 1.0, datetime(2024, 1, 1, 0, 0, 0))


def seed_entity(conn: sqlite3.Connection) -> int:
    return queries.create_entity(conn, "Test Broker", EntityType.BROKER)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMakeTrigger(unittest.TestCase):
    def test_one_off_future(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "ONE_OFF",
            "start_date": date(2099, 1, 1),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, DateTrigger)

    def test_one_off_past(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "ONE_OFF",
            "start_date": date(2020, 1, 1),
            "custom_cron": None,
        })
        self.assertIsNone(trigger)

    def test_daily(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "DAILY",
            "start_date": date(2025, 1, 1),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_weekly(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "WEEKLY",
            "start_date": date(2025, 6, 1),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_monthly(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "MONTHLY",
            "start_date": date(2025, 6, 15),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_quarterly(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "QUARTERLY",
            "start_date": date(2025, 6, 15),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_annually(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "ANNUALLY",
            "start_date": date(2025, 6, 15),
            "custom_cron": None,
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_custom_with_cron(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "CUSTOM",
            "start_date": date(2025, 1, 1),
            "custom_cron": "0 12 * * 1",
        })
        self.assertIsInstance(trigger, CronTrigger)

    def test_custom_without_cron(self):
        from scheduler.scheduler import _make_trigger
        trigger = _make_trigger({
            "id": 1,
            "periodicity_type": "CUSTOM",
            "start_date": date(2025, 1, 1),
            "custom_cron": None,
        })
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
            self.conn, "Monthly DCA", "2025-01-01", "MONTHLY",
        )
        from scheduler.scheduler import sync_schedule, get_scheduler
        sync_schedule(sid)
        sched = get_scheduler()
        job = sched.get_job(f"schedule_{sid}")
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "Monthly DCA")

    def test_sync_nonexistent_schedule(self):
        from scheduler.scheduler import sync_schedule, get_scheduler
        sync_schedule(999)
        sched = get_scheduler()
        self.assertIsNone(sched.get_job("schedule_999"))

    def test_remove_removes_job(self):
        sid = queries.create_schedule(
            self.conn, "To Remove", "2025-01-01", "WEEKLY",
        )
        from scheduler.scheduler import sync_schedule, remove_schedule, get_scheduler
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
            self.conn, "Monthly DCA", "2025-01-01", "MONTHLY",
            entity_id=self.eid, currency="USD", type_="INVESTMENT_BUY",
            total_value=500.0,
        )
        from scheduler.scheduler import _clone_tx
        new_id = _clone_tx(sid)
        self.assertIsNotNone(new_id)
        tx = queries.get_transaction(self.conn, new_id)
        self.assertEqual(tx["entity_id"], self.eid)
        self.assertEqual(tx["currency"], "USD")
        self.assertEqual(tx["type"], "INVESTMENT_BUY")
        self.assertEqual(tx["total_value"], 500.0)

    def test_clone_skips_soft_deleted_entity(self):
        sid = queries.create_schedule(
            self.conn, "Monthly DCA", "2025-01-01", "MONTHLY",
            entity_id=self.eid,
        )
        queries.delete_entity(self.conn, self.eid)
        from scheduler.scheduler import _clone_tx
        new_id = _clone_tx(sid)
        self.assertIsNone(new_id)

    def test_clone_skips_when_entity_id_none(self):
        sid = queries.create_schedule(
            self.conn, "No Entity", "2025-01-01", "MONTHLY",
        )
        from scheduler.scheduler import _clone_tx
        new_id = _clone_tx(sid)
        self.assertIsNone(new_id)

    def test_execute_schedule_creates_transaction(self):
        """Scheduler should create transaction when executed"""
        sid = queries.create_schedule(
            self.conn, "Test Schedule", "2025-01-01", "MONTHLY",
            entity_id=self.eid, currency="USD", type_="MONEY_IN",
            total_value=100.0,
        )
        
        # Verify no transactions before execution
        tx_before = self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE entity_id = ?",
            (self.eid,)
        ).fetchone()[0]
        self.assertEqual(tx_before, 0)
        
        # Execute schedule
        from scheduler.scheduler import execute_schedule
        execute_schedule(sid)
        
        # Verify transaction was created
        tx_after = self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE entity_id = ?",
            (self.eid,)
        ).fetchone()[0]
        self.assertEqual(tx_after, 1)
        
        # Verify transaction details
        tx = self.conn.execute(
            "SELECT * FROM transactions WHERE entity_id = ? ORDER BY id DESC LIMIT 1",
            (self.eid,)
        ).fetchone()
        self.assertEqual(tx["total_value"], 100.0)
        self.assertEqual(tx["type"], "MONEY_IN")
        self.assertEqual(tx["currency"], "USD")

    def test_execute_schedule_respects_end_date(self):
        """Scheduler should NOT create transaction if end_date has passed"""
        past_end = (date.today() - timedelta(days=1)).isoformat()
        sid = queries.create_schedule(
            self.conn, "Expired Schedule", "2025-01-01", "MONTHLY",
            end_date=past_end,
            entity_id=self.eid, currency="USD", type_="MONEY_IN",
            total_value=100.0,
        )
        
        from scheduler.scheduler import execute_schedule
        execute_schedule(sid)
        
        tx_count = self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE entity_id = ?",
            (self.eid,)
        ).fetchone()[0]
        self.assertEqual(tx_count, 0)


class TestInitScheduler(unittest.TestCase):
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

    def test_init_loads_schedules(self):
        queries.create_schedule(self.conn, "S1", "2025-01-01", "MONTHLY")
        queries.create_schedule(self.conn, "S2", "2025-01-01", "WEEKLY")
        from scheduler.scheduler import init_scheduler, get_scheduler
        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 2)

    def test_init_empty(self):
        from scheduler.scheduler import init_scheduler, get_scheduler
        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 0)

    def test_init_skips_past_one_off(self):
        queries.create_schedule(self.conn, "Past", "2020-01-01", "ONE_OFF")
        from scheduler.scheduler import init_scheduler, get_scheduler
        init_scheduler()
        sched = get_scheduler()
        self.assertEqual(len(sched.get_jobs()), 0)


if __name__ == "__main__":
    unittest.main()
