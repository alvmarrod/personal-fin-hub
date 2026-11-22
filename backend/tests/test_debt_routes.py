import unittest
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from models import (
    DayCount,
    DebtDetail,
    DebtDirection,
    DebtNextPayment,
    DebtResponse,
    DebtStatus,
    DebtSummary,
    DisbursementMode,
    InstallmentMode,
    RateResetMode,
)
from routes.debt import router
from services.debt_svc import DebtNotFound, DebtValidationError

app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)


def _response(debt_id: int = 1) -> DebtResponse:
    return DebtResponse(
        id=debt_id,
        direction=DebtDirection.PAYABLE,
        counterparty_name="Bank",
        currency="EUR",
        principal=10000.0,
        start_date=date(2026, 1, 1),
        installment_mode=InstallmentMode.EQUAL_PAYMENT,
        day_count=DayCount.MONTHLY,
        rate_reset_mode=RateResetMode.RECALCULATE_INSTALLMENT,
        disbursement_mode=DisbursementMode.NONE,
        status=DebtStatus.ACTIVE,
    )


def _detail(debt_id: int = 1) -> DebtDetail:
    return DebtDetail(**_response(debt_id).model_dump(), rates=[], payments=[], plan=[])


class DebtRoutesTest(unittest.TestCase):
    def test_list(self):
        with patch("routes.debt.debt_svc.list_debts", return_value=[_response()]):
            resp = client.get("/api/v1/debt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["counterparty_name"], "Bank")

    def test_summary_requires_a_currency(self):
        self.assertEqual(client.get("/api/v1/debt/summary").status_code, 422)

    def test_summary(self):
        summary = DebtSummary(
            display_currency="EUR",
            payable=10000.0,
            receivable=0.0,
            payable_count=1,
            receivable_count=0,
            payable_accrued_interest=10.0,
            receivable_accrued_interest=0.0,
            next_payable=DebtNextPayment(debt_id=1, counterparty_name="Bank", due_date=date(2026, 2, 1), amount=200.0),
        )
        with patch("routes.debt.debt_svc.summary", return_value=summary):
            resp = client.get("/api/v1/debt/summary?display_currency=EUR")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["payable"], 10000.0)

    def test_get_not_found(self):
        with patch("routes.debt.debt_svc.get", side_effect=DebtNotFound("missing")):
            resp = client.get("/api/v1/debt/9")
        self.assertEqual(resp.status_code, 404)

    def test_create_validation_maps_to_422(self):
        with patch("routes.debt.debt_svc.create", side_effect=DebtValidationError("bad")):
            resp = client.post("/api/v1/debt", json={"direction": "payable"})
        self.assertEqual(resp.status_code, 422)

    def test_payment_requires_an_entity(self):
        body = {"paid_at": "2026-02-01", "amount": 200.0}
        resp = client.post("/api/v1/debt/1/payments", json=body)
        self.assertEqual(resp.status_code, 422)

    def test_settle(self):
        with patch("routes.debt.debt_svc.settle", return_value=_detail()) as settle:
            resp = client.post(
                "/api/v1/debt/1/settle",
                json={"settled_at": "2026-02-01", "entity_id": 1, "amount": 10100.0},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(settle.call_args.args[1].amount, 10100.0)

    def test_delete(self):
        with patch("routes.debt.debt_svc.delete", return_value=None):
            resp = client.delete("/api/v1/debt/1")
        self.assertEqual(resp.status_code, 204)

    def test_counterparties(self):
        with patch("routes.debt.debt_svc.counterparties", return_value=["Bank", "Ana"]):
            resp = client.get("/api/v1/debt/counterparties")
        self.assertEqual(resp.json(), ["Bank", "Ana"])

    def test_plan_import(self):
        entry = {
            "due_date": "2026-02-01",
            "payment_amount": 200.0,
            "principal_amount": 150.0,
            "interest_amount": 50.0,
        }
        with patch("routes.debt.debt_svc.import_plan", return_value=[]) as import_plan:
            resp = client.put("/api/v1/debt/1/plan", json={"entries": [entry]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(import_plan.call_args.args[1].entries[0].payment_amount, 200.0)
