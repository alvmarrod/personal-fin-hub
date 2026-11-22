import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from db.connection import ProfileScopedConnection

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

DEBT = {
    "principal": 10000.0,
    "start_date": "2026-01-01",
    "day_count": "monthly",
    "status": "active",
    "maturity_date": "2027-01-01",
    "term_months": 12,
    "installment_mode": "manual",
    "installment_amount": None,
    "principal_per_installment": None,
    "rate_reset_mode": "recalculate_installment",
}


def in_memory_db() -> ProfileScopedConnection:
    conn: ProfileScopedConnection = sqlite3.connect(
        ":memory:", factory=ProfileScopedConnection, check_same_thread=False
    )
    conn.profile_id = 1
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("INSERT INTO profiles (id, name) VALUES (1, 'Default')")
    conn.execute("INSERT INTO currencies (code, base_code, rate, timestamp) VALUES ('EUR', 'EUR', 1.0, '2025-01-01')")
    conn.execute("INSERT INTO entities (id, name, entity_type, profile_id) VALUES (1, 'Bank', 'BANK', 1)")
    conn.commit()
    return conn


class TestDebtAccrual(unittest.TestCase):
    def setUp(self):
        from services import debt_svc

        self.svc = debt_svc

    def test_monthly_full_month(self):
        interest = self.svc._interest_between(
            DEBT,
            [{"effective_from": "2026-01-01", "annual_rate": 12.0}],
            10000.0,
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        self.assertAlmostEqual(interest, 100.0, places=6)

    def test_actual_365(self):
        debt = {**DEBT, "day_count": "actual_365"}
        interest = self.svc._interest_between(
            debt,
            [{"effective_from": "2026-01-01", "annual_rate": 12.0}],
            10000.0,
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        self.assertAlmostEqual(interest, 10000 * 0.12 * 31 / 365, places=6)

    def test_thirty_360(self):
        debt = {**DEBT, "day_count": "thirty_360"}
        interest = self.svc._interest_between(
            debt,
            [{"effective_from": "2026-01-01", "annual_rate": 12.0}],
            10000.0,
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        self.assertAlmostEqual(interest, 100.0, places=6)

    def test_rate_change_mid_period(self):
        rates = [
            {"effective_from": "2026-01-01", "annual_rate": 12.0},
            {"effective_from": "2026-01-16", "annual_rate": 6.0},
        ]
        interest = self.svc._interest_between(DEBT, rates, 10000.0, date(2026, 1, 1), date(2026, 2, 1))
        expected = 10000 * 0.12 * (15 / 31) / 12 + 10000 * 0.06 * (16 / 31) / 12
        self.assertAlmostEqual(interest, expected, places=6)

    def test_zero_rate_accrues_nothing(self):
        interest = self.svc._interest_between(
            DEBT,
            [{"effective_from": "2026-01-01", "annual_rate": 0.0}],
            10000.0,
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        self.assertEqual(interest, 0.0)


class TestDebtService(unittest.TestCase):
    def setUp(self):
        from services import debt_svc

        self.svc = debt_svc
        self.db = in_memory_db()
        self.patcher = patch("services.debt_svc.get_db", return_value=self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.currency_patcher = patch("services.currency_svc.get_db", return_value=self.db)
        self.currency_patcher.start()
        self.addCleanup(self.currency_patcher.stop)

    def tearDown(self):
        self.db.close()

    def _create(self, **overrides):
        from models import DebtCreate

        body = {
            "direction": "payable",
            "counterparty_name": "Bank",
            "currency": "EUR",
            "principal": 10000.0,
            "start_date": date(2026, 1, 1),
            "annual_rate": 12.0,
            "term_months": 12,
            "maturity_date": date(2027, 1, 1),
            "installment_mode": "manual",
            **overrides,
        }
        return self.svc.create(DebtCreate(**body))

    def test_create_writes_the_first_rate_and_pocket_transaction(self):
        debt = self._create(disbursement_mode="pocket", disbursement_entity_id=1, disbursement_date=date(2026, 1, 1))

        self.assertEqual(debt.status, "active")
        self.assertEqual(debt.current_rate, 12.0)
        self.assertEqual(len(debt.rates), 1)
        tx = self.db.execute("SELECT type, total_value FROM transactions").fetchone()
        self.assertEqual(tx["type"], "DEBT_IN")
        self.assertEqual(tx["total_value"], 10000.0)

    def test_receivable_disbursement_is_cash_out(self):
        debt = self._create(
            direction="receivable",
            counterparty_name="Ana",
            principal=500.0,
            disbursement_mode="pocket",
            disbursement_entity_id=1,
            disbursement_date=date(2026, 1, 1),
        )
        self.assertEqual(debt.outstanding_principal, 500.0)
        tx = self.db.execute("SELECT type, total_value FROM transactions").fetchone()
        self.assertEqual(tx["type"], "DEBT_OUT")

    def test_payment_splits_interest_first(self):
        from models import DebtPaymentBody

        self._create()
        result = self.svc.record_payment(
            1,
            DebtPaymentBody(paid_at=date(2026, 2, 1), entity_id=1, amount=200.0),
        )
        payment = result.payments[0]
        self.assertAlmostEqual(payment.interest_amount, 100.0, places=2)
        self.assertAlmostEqual(payment.principal_amount, 100.0, places=2)
        self.assertAlmostEqual(result.outstanding_principal, 9900.0, places=2)
        tx = self.db.execute("SELECT type, total_value FROM transactions").fetchone()
        self.assertEqual(tx["type"], "DEBT_OUT")

    def test_principal_only_payment_skips_interest(self):
        from models import DebtPaymentBody

        self._create()
        result = self.svc.record_payment(
            1,
            DebtPaymentBody(paid_at=date(2026, 2, 1), entity_id=1, amount=200.0, principal_only=True),
        )
        payment = result.payments[0]
        self.assertEqual(payment.interest_amount, 0.0)
        self.assertEqual(payment.principal_amount, 200.0)

    def test_payment_below_accrued_interest_is_rejected(self):
        from models import DebtPaymentBody

        self._create()
        with self.assertRaises(self.svc.DebtValidationError):
            self.svc.record_payment(1, DebtPaymentBody(paid_at=date(2026, 2, 1), entity_id=1, amount=50.0))

    def test_full_payment_settles_and_delete_reopens(self):
        from models import DebtPaymentBody

        self._create()
        result = self.svc.record_payment(1, DebtPaymentBody(paid_at=date(2026, 2, 1), entity_id=1, amount=10100.0))
        self.assertEqual(result.status, "settled")
        self.assertEqual(result.outstanding_principal, 0.0)

        reopened = self.svc.delete_payment(1, result.payments[0].id)
        self.assertEqual(reopened.status, "active")
        self.assertEqual(reopened.outstanding_principal, 10000.0)

    def test_settle_keeps_the_override_as_adjustment(self):
        from models import DebtSettleBody

        self._create()
        result = self.svc.settle(1, DebtSettleBody(settled_at=date(2026, 2, 1), entity_id=1, amount=10150.0))
        self.assertEqual(result.status, "settled")
        self.assertAlmostEqual(result.settlement_adjustment, 50.0, places=2)
        self.assertAlmostEqual(result.payments[0].interest_amount, 100.0, places=2)

    def test_equal_payment_projects_an_annuity(self):
        debt = self._create(installment_mode="equal_payment", installment_amount=None)
        self.assertIsNotNone(debt.next_payment_date)
        self.assertGreater(debt.next_payment_amount or 0, 800.0)

    def test_summary_groups_by_direction(self):
        self._create()
        self._create(
            direction="receivable",
            counterparty_name="Ana",
            principal=500.0,
            disbursement_mode="none",
        )
        summary = self.svc.summary("EUR")
        self.assertEqual(summary.payable, 10000.0)
        self.assertEqual(summary.receivable, 500.0)
        self.assertEqual(summary.payable_count, 1)
        self.assertEqual(summary.receivable_count, 1)
