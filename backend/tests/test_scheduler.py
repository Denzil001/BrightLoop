from contextlib import nullcontext
from datetime import date, timedelta
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.datetime_utils import get_business_now
from app.core.config import get_settings
from app.models.billing import BillingOutcome, BillingRun, EmailAttempt
from app.models.invoices import Invoice
from app.models.scheduler import SchedulerState
from app.models.subscriptions import SubscriptionEvent, SubscriptionPause, SubscriptionTerm
from app.services import billing_runs
from app.services.billing import process_next_period
from app.services.scheduler import LOCK_KEY, recover_interrupted, scheduler_status, scheduler_tick
from app.services.billing_runs import run_lock_key
from test_billing import contract
from test_billing_concurrency import committed_case
from test_subscriptions import draft_data


@pytest.mark.parametrize("policy,paused,expected", [(True, False, "CLOSED"), (False, False, "ACTIVE"), (True, True, "PAUSED")])
def test_auto_close_frozen_policy_pause_and_historical_billing(db, admin_auth, draft_data, policy, paused, expected):
    sub = contract(db, admin_auth["user"], draft_data)
    term = db.scalar(select(SubscriptionTerm).where(SubscriptionTerm.subscription_id == sub.id))
    term.auto_close_on_expiry = policy
    sub.plan.auto_close_on_expiry = not policy  # Live catalog cannot change the accepted policy.
    if paused:
        pause = SubscriptionEvent(subscription_id=sub.id, term_id=term.id, action="PAUSE",
            effective_date=date(2025, 2, 28), applied_at=get_business_now(), payload={})
        db.add(pause)
        db.flush()
        db.add(SubscriptionPause(term_id=term.id, pause_event_id=pause.id,
            start_date=date(2025, 2, 28), original_expiry_date=term.expiry_date))
        sub.state = "PAUSED"
    db.commit()
    for _ in range(4):
        process_next_period(db, sub.id, date(2025, 5, 1))
        db.commit()
    assert sub.state == expected
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == sub.id)) == (1 if paused else 3)
    assert db.scalar(select(func.count()).select_from(SubscriptionEvent).where(
        SubscriptionEvent.subscription_id == sub.id, SubscriptionEvent.action == "AUTO_CLOSE")) == int(expected == "CLOSED")


def test_scheduler_shared_engine_interruption_recovery_and_unknown_delivery(db, admin_auth, draft_data, monkeypatch):
    sub = contract(db, admin_auth["user"], draft_data)
    original = billing_runs.process_next_period
    calls = 0

    def crash_after_commit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("Simulated process loss after one committed period")
        return original(*args, **kwargs)

    monkeypatch.setattr(billing_runs, "process_next_period", crash_after_commit)
    options = dict(session_factory=lambda: nullcontext(db), lock_engine=test_engine,
        as_of=date(2025, 4, 20), subscription_id=sub.id)
    with pytest.raises(KeyboardInterrupt):
        scheduler_tick(**options)
    interrupted = db.scalar(select(BillingRun).where(BillingRun.trigger == "SCHEDULED"))
    assert interrupted.state == "RUNNING"
    invoice = db.scalar(select(Invoice).where(Invoice.subscription_id == sub.id))
    attempt = EmailAttempt(invoice_id=invoice.id, kind="INVOICE_SEND", status="PENDING",
        attempted_at=get_business_now() - timedelta(minutes=20))
    db.add(attempt)
    db.commit()
    monkeypatch.setattr(billing_runs, "process_next_period", original)
    result = scheduler_tick(**options)
    assert result["created"] == 2
    assert interrupted.state == "INTERRUPTED"
    assert interrupted.summary_counts["created"] == 1
    assert attempt.status == "UNKNOWN"
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == sub.id)) == 3
    assert scheduler_tick(**options)["created"] == 0
    assert scheduler_status(db)["active"] is True
    state = db.get(SchedulerState, 1)
    state.heartbeat_at -= timedelta(hours=1)
    assert scheduler_status(db)["state"] == "STALE"


def test_second_postgresql_worker_skips_while_lock_is_held(db):
    with test_engine.connect() as other_worker:
        assert other_worker.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            assert scheduler_tick(session_factory=lambda: nullcontext(db), lock_engine=test_engine)["state"] == "SKIPPED"
            assert db.get(SchedulerState, 1) is None
        finally:
            other_worker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            other_worker.commit()


def test_never_started_scheduler_reports_unconfigured(db):
    assert scheduler_status(db)["configured"] is False


def test_recovery_distinguishes_live_manual_run_from_orphaned_cli_run(db):
    live = BillingRun(trigger="MANUAL", state="RUNNING", as_of_date=date(2025, 1, 31))
    orphan = BillingRun(trigger="CLI", state="RUNNING", as_of_date=date(2025, 1, 31))
    db.add_all([live, orphan])
    db.commit()
    with test_engine.connect() as owner:
        owner.execute(text("SELECT pg_advisory_lock(:key)"), {"key": run_lock_key(live.id)})
        owner.commit()
        try:
            recover_interrupted(db)
            assert live.state == "RUNNING"
            assert orphan.state == "INTERRUPTED"
            assert orphan.summary_counts["created"] == 0
        finally:
            owner.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": run_lock_key(live.id)})
            owner.commit()


def test_real_timer_process_runs_twice_without_duplicate_periods():
    """Run the actual worker entry point against only the isolated test DB."""
    with committed_case(1) as ids:
        with Session(test_engine) as db:
            before = set(db.scalars(select(BillingRun.id)))
        try:
            env = os.environ.copy()
            env["DATABASE_URL"] = get_settings().TEST_DATABASE_URL
            result = subprocess.run([sys.executable, "scripts/run_scheduler.py", "--interval-seconds", "10", "--ticks", "2"],
                cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=40)
            assert result.returncode == 0, "Actual scheduler process failed; no private environment values are emitted."
            with Session(test_engine) as db:
                runs = list(db.scalars(select(BillingRun).where(BillingRun.trigger == "SCHEDULED").order_by(BillingRun.started_at)))
                assert len(runs) == 2
                assert [run.summary_counts["created"] for run in runs] == [3, 0]
                assert all(run.state == "COMPLETED" for run in runs)
                assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == ids["subscriptions"][0])) == 3
                assert scheduler_status(db)["state"] == "STOPPED"
                assert scheduler_status(db)["active"] is False
        finally:
            with Session(test_engine) as db:
                run_ids = set(db.scalars(select(BillingRun.id))) - before
                db.execute(delete(SchedulerState).where(SchedulerState.last_run_id.in_(run_ids)))
                db.execute(delete(BillingOutcome).where(BillingOutcome.run_id.in_(run_ids)))
                db.execute(update(BillingRun).where(BillingRun.id.in_(run_ids)).values(retry_of_id=None))
                db.execute(delete(BillingRun).where(BillingRun.id.in_(run_ids)))
                db.commit()
