from contextlib import nullcontext
from datetime import date, timedelta

from sqlalchemy import func, select

from app.api.v1.endpoints.billing_runs import get_billing_session_factory
from app.core.datetime_utils import get_business_today
from app.main import app
from app.models.billing import BillingOutcome, BillingRun
from app.models.invoices import Invoice
from app.services import billing_runs
from app.services.billing import BillingFailure
from test_billing import contract
from test_subscriptions import draft_data, headers


def test_bounded_run_continuation_and_api_roles(db, client, admin_auth, staff_auth, customer_auth, draft_data):
    contract(db, admin_auth["user"], draft_data)
    app.dependency_overrides[get_billing_session_factory] = lambda: lambda: nullcontext(db)
    body = {"as_of_date": "2025-04-20", "max_periods": 1}
    for denied in (staff_auth, customer_auth):
        assert client.post("/api/v1/billing-runs", json=body, headers=headers(denied)).status_code == 403
    assert client.post("/api/v1/billing-runs", json={**body, "as_of_date": (get_business_today() + timedelta(days=1)).isoformat()}, headers=headers(admin_auth)).status_code == 422
    for index in range(3):
        response = client.post("/api/v1/billing-runs", json=body, headers=headers(admin_auth))
        assert response.status_code == 201, response.text
        run = response.json()
        assert run["summary"]["created"] == 1
        assert run["summary"]["has_more"] == (index < 2)
        assert run["retry_of_id"] == body.get("retry_of_id")
        assert client.get(f"/api/v1/billing-runs/{run['id']}", headers=headers(admin_auth)).json()["outcomes"][0]["state"] == "CREATED"
        body["retry_of_id"] = run["id"]
    assert db.scalar(select(func.count()).select_from(Invoice)) == 3


def test_failed_period_logs_safe_error_and_retry_preserves_committed_work(db, admin_auth, draft_data, monkeypatch):
    subscription = contract(db, admin_auth["user"], draft_data)
    original = billing_runs.process_next_period

    def fail_second(db, subscription_id, as_of, run_id, actor_id):
        count = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == subscription_id))
        if count == 1:
            raise BillingFailure(date(2025, 2, 28), "PERIOD_WRITE_FAILED")
        return original(db, subscription_id, as_of, run_id, actor_id)

    monkeypatch.setattr(billing_runs, "process_next_period", fail_second)
    run_id = billing_runs.run_billing(date(2025, 4, 20), admin_auth["user"].id, session_factory=lambda: nullcontext(db))
    run = db.get(BillingRun, run_id)
    assert run.state == "FAILED"
    assert run.summary_counts["created"] == 1
    assert run.summary_counts["failed"] == 1
    failure = db.scalar(select(BillingOutcome).where(BillingOutcome.state == "FAILED"))
    assert failure.safe_error_code == "PERIOD_WRITE_FAILED"
    assert failure.period_start == date(2025, 2, 28)
    assert db.scalar(select(func.count()).select_from(Invoice)) == 1
    monkeypatch.setattr(billing_runs, "process_next_period", original)
    retry = billing_runs.run_billing(date(2025, 4, 20), admin_auth["user"].id, session_factory=lambda: nullcontext(db))
    assert db.get(BillingRun, retry).summary_counts["created"] == 2
    assert db.scalar(select(func.count()).select_from(Invoice)) == 3


def test_targeted_recovery_leaves_other_subscriptions_untouched(db, admin_auth, draft_data):
    first = contract(db, admin_auth["user"], draft_data)
    second = contract(db, admin_auth["user"], draft_data)
    run_id = billing_runs.run_billing(date(2025, 4, 20), admin_auth["user"].id,
        session_factory=lambda: nullcontext(db), subscription_id=second.id)
    summary = db.get(BillingRun, run_id).summary_counts
    assert summary["target_subscription_id"] == str(second.id)
    assert summary["created"] == 3
    assert summary["subscriptions_scanned"] == 1
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == first.id)) == 0
