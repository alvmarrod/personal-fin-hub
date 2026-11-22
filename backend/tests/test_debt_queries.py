import sqlite3
import unittest
from pathlib import Path

from db.connection import ProfileScopedConnection

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def in_memory_db() -> ProfileScopedConnection:
    conn: ProfileScopedConnection = sqlite3.connect(
        ":memory:", factory=ProfileScopedConnection, check_same_thread=False
    )
    conn.profile_id = None
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
    conn.execute("INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01')")
    conn.execute("INSERT INTO entities (id, name, entity_type) VALUES (1, 'Bank', 'BANK')")
    conn.commit()
    return conn


DEBT = {
    "direction": "payable",
    "counterparty_name": "Bank",
    "description": "Mortgage",
    "currency": "EUR",
    "principal": 10000.0,
    "start_date": "2026-01-01",
    "term_months": 60,
    "maturity_date": "2031-01-01",
    "installment_mode": "equal_payment",
    "installment_amount": 200.0,
    "principal_per_installment": None,
    "day_count": "monthly",
    "rate_reset_mode": "recalculate_installment",
    "review_period_months": 12,
    "disbursement_mode": "none",
    "disbursement_entity_id": None,
    "disbursement_date": None,
    "status": "active",
    "settled_at": None,
    "settled_amount": None,
    "settlement_adjustment": None,
    "notes": None,
}


class TestDebtQueries(unittest.TestCase):
    def setUp(self):
        self.conn = in_memory_db()
        self.conn.profile_id = 1
        from db import debt_queries as q

        self.q = q

    def tearDown(self):
        self.conn.close()

    def _insert(self, **overrides):
        fields = {**DEBT, **overrides}
        return self.q.insert_debt(self.conn, **fields)

    def test_crud_and_profile_scope(self):
        debt_id = self._insert()
        row = self.q.get_debt(self.conn, debt_id)
        self.assertEqual(row["counterparty_name"], "Bank")

        self.q.update_debt(self.conn, debt_id, counterparty_name="Bank Two")
        self.assertEqual(self.q.get_debt(self.conn, debt_id)["counterparty_name"], "Bank Two")

        self.conn.profile_id = 2
        self.assertIsNone(self.q.get_debt(self.conn, debt_id))
        self.assertEqual(self.q.list_debts(self.conn), [])
        self.conn.profile_id = 1

        self.assertEqual(self.q.delete_debt(self.conn, debt_id), 1)
        self.assertIsNone(self.q.get_debt(self.conn, debt_id))

    def test_filters_and_order(self):
        first = self._insert(start_date="2026-01-01")
        second = self._insert(start_date="2026-06-01", direction="receivable", counterparty_name="Ana")
        self.q.update_debt(self.conn, first, status="settled")

        self.assertEqual([d["id"] for d in self.q.list_debts(self.conn)], [second, first])
        self.assertEqual([d["id"] for d in self.q.list_debts(self.conn, direction="receivable")], [second])
        self.assertEqual([d["id"] for d in self.q.list_debts(self.conn, status="settled")], [first])

    def test_rates_resolve_the_latest_on_or_before(self):
        debt_id = self._insert()
        self.q.insert_rate(self.conn, debt_id, "2026-01-01", 3.0)
        self.q.insert_rate(self.conn, debt_id, "2026-06-01", 3.5)

        self.assertEqual(self.q.list_rates(self.conn, debt_id)[1]["annual_rate"], 3.5)
        self.assertEqual(self.q.get_rate_on(self.conn, debt_id, "2025-12-31"), None)
        self.assertEqual(self.q.get_rate_on(self.conn, debt_id, "2026-01-01")["annual_rate"], 3.0)
        self.assertEqual(self.q.get_rate_on(self.conn, debt_id, "2026-06-15")["annual_rate"], 3.5)

    def test_payments_and_transaction_link(self):
        debt_id = self._insert()
        payment_id = self.q.insert_payment(
            self.conn,
            debt_id,
            paid_at="2026-02-01",
            amount=200.0,
            principal_amount=150.0,
            interest_amount=50.0,
            fees_amount=0.0,
            insurance_amount=0.0,
            other_amount=0.0,
            kind="regular",
            transaction_id=None,
        )
        self.assertEqual(self.q.list_payments(self.conn, debt_id)[0]["amount"], 200.0)
        self.assertIsNone(self.q.get_payment_by_transaction(self.conn, 1))
        self.assertEqual(self.q.delete_payment(self.conn, payment_id), 1)
        self.assertEqual(self.q.list_payments(self.conn, debt_id), [])

    def test_plan_replace_from_a_date(self):
        debt_id = self._insert()
        for period, due in enumerate(("2026-02-01", "2026-03-01", "2026-04-01"), start=1):
            self.q.insert_plan_entry(self.conn, debt_id, period, due, 200.0, 150.0, 50.0)

        self.assertEqual(self.q.delete_plan_entries_from(self.conn, debt_id, "2026-03-01"), 2)
        self.assertEqual([r["due_date"] for r in self.q.list_plan_entries(self.conn, debt_id)], ["2026-02-01"])

    def test_counterparties_are_deduped_case_insensitively(self):
        self._insert(counterparty_name="Bank", start_date="2026-01-01")
        self._insert(counterparty_name="bank", start_date="2026-05-01")
        self._insert(counterparty_name="Ana", start_date="2026-03-01")

        self.assertEqual(self.q.list_counterparties(self.conn), ["bank", "Ana"])
