"""Committed PostgreSQL batch: 300 due plus paused/closed/future/draft records."""
from datetime import date
import json
from pathlib import Path
from time import perf_counter
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.datetime_utils import get_business_now
from app.models.billing import BillingOutcome, BillingRun
from app.models.invoices import Invoice
from app.models.subscriptions import AgreementVersion, Subscription, SubscriptionEvent, SubscriptionPause, SubscriptionTerm
from app.models.users import User
from app.schemas.subscriptions import SubscriptionCommand, SubscriptionDraft
from app.services import billing_runs
from app.services.billing import BillingFailure, process_next_period
from app.services.subscriptions import create_draft, execute_command
from test_billing_concurrency import committed_case


def test_300_due_mixed_batch_committed_failure_recovery_and_replay(monkeypatch):
    started = perf_counter()
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(Subscription)) == 0, "This fixture requires the isolated test database without unrelated committed subscriptions."
    with committed_case(315) as ids:
        due = ids["subscriptions"][:300]
        paused = ids["subscriptions"][300:305]
        closed = ids["subscriptions"][305:310]
        future = ids["subscriptions"][310:315]
        as_of = date(2025, 2, 28)
        try:
            with Session(test_engine) as db:
                actor = db.get(User, ids["actor"])
                for index, sub_id in enumerate(ids["subscriptions"][:315]):
                    sub = db.get(Subscription, sub_id)
                    term = db.scalar(select(SubscriptionTerm).where(SubscriptionTerm.subscription_id == sub_id))
                    if index < 30:
                        sub.state = "CLOSED"  # Current closure cannot erase historical owed service.
                    if 30 <= index < 60 or sub_id in paused:
                        stop = date(2025, 3, 31) if index < 60 else as_of
                        event = SubscriptionEvent(subscription_id=sub_id, term_id=term.id, action="PAUSE",
                            effective_date=stop, applied_at=get_business_now(), actor_id=actor.id, payload={"fixture": True})
                        db.add(event)
                        db.flush()
                        db.add(SubscriptionPause(term_id=term.id, start_date=stop,
                            original_expiry_date=term.expiry_date, pause_event_id=event.id))
                        sub.state, sub.next_billing_date = "PAUSED", None
                    if sub_id in closed:
                        term.expiry_date, sub.state, sub.next_billing_date = as_of, "CLOSED", None
                    if sub_id in future:
                        term.start_date = term.original_anchor_date = date(2025, 3, 31)
                        agreement = db.get(AgreementVersion, term.source_version_id)
                        agreement.proposed_start_date = agreement.effective_from = term.start_date
                        sub.state, sub.next_billing_date = "CONFIRMED", term.start_date
                for index in range(10):
                    sub = create_draft(db, SubscriptionDraft(customer_id=ids["customer"], plan_id=ids["plan"],
                        seat_quantity=1, start_date=date(2025, 1, 31), expiry_date=date(2025, 4, 30)), actor)
                    ids["subscriptions"].append(sub.id)
                    if index >= 5:
                        execute_command(db, sub, SubscriptionCommand(action="ISSUE", expected_version=sub.version,
                            request_key=uuid.uuid4().hex), actor)
                db.commit()
            # Fully account for the already-paused/closed cohort before the scan.
            for sub_id in paused + closed:
                with Session(test_engine) as db:
                    assert process_next_period(db, sub_id, as_of).state == "CREATED"
                    db.commit()
            failed_sub = due[5]
            original = billing_runs.process_next_period
            def fail_second_period(db, sub_id, run_date, run_id, actor_id):
                if sub_id == failed_sub and db.scalar(select(Invoice.id).where(
                    Invoice.subscription_id == sub_id, Invoice.period_start == date(2025, 1, 31))):
                    raise BillingFailure(as_of, "PERIOD_WRITE_FAILED")
                return original(db, sub_id, run_date, run_id, actor_id)
            monkeypatch.setattr(billing_runs, "process_next_period", fail_second_period)

            def drain():
                cursor, previous, summaries = None, None, []
                for _ in range(30):
                    run_id = billing_runs.run_billing(as_of, actor_id=ids["actor"], trigger="CLI",
                        after_subscription_id=cursor, retry_of_id=previous, session_factory=lambda: Session(test_engine))
                    with Session(test_engine) as db:
                        run = db.get(BillingRun, run_id)
                        summary = run.summary_counts
                        summaries.append(summary)
                        assert summary["created"] <= 100 and summary["subscriptions_scanned"] <= 100
                        assert run.state == ("FAILED" if summary["failed"] else "COMPLETED")
                    previous = run_id
                    if not summary["has_more"]:
                        return summaries
                    cursor = uuid.UUID(summary["continue_after_id"]) if summary["continue_after_id"] else None
                raise AssertionError("Bounded continuation did not terminate.")

            first = drain()
            assert sum(item["created"] for item in first) == 599
            assert sum(item["failed"] for item in first) == 1
            with Session(test_engine) as db:
                before_retry = {row.id: (row.period_start, row.total) for row in db.scalars(select(Invoice))}
                assert len(before_retry) == 609
                failed = list(db.scalars(select(BillingOutcome).where(BillingOutcome.state == "FAILED")))
                assert len(failed) == 1 and failed[0].subscription_id == failed_sub
                assert failed[0].period_start == as_of and failed[0].safe_error_code == "PERIOD_WRITE_FAILED"
            monkeypatch.setattr(billing_runs, "process_next_period", original)
            retry = drain()
            assert sum(item["created"] for item in retry) == 1
            assert sum(item["failed"] for item in retry) == 0
            expected = {(sub_id, first_date) for sub_id in due for first_date in (date(2025, 1, 31), as_of)}
            expected |= {(sub_id, date(2025, 1, 31)) for sub_id in paused + closed}
            with Session(test_engine) as db:
                rows = list(db.scalars(select(Invoice)))
                assert len(rows) == len(expected) == 610
                assert {(row.subscription_id, row.period_start) for row in rows} == expected
                assert all((row.period_start, row.total) == before_retry[row.id] for row in rows if row.id in before_retry)
                final_ids = {row.id for row in rows}
                assert not db.scalar(select(Invoice.id).where(Invoice.subscription_id.in_(future + ids["subscriptions"][315:])).limit(1))
            replay = drain()
            assert sum(item["created"] for item in replay) == sum(item["failed"] for item in replay) == 0
            with Session(test_engine) as db:
                assert set(db.scalars(select(Invoice.id))) == final_ids
            report = {"database": "isolated brightloop_test", "subscriptions": 325, "due_subscriptions": 300,
                "expected_due_periods": 600, "already_billed_paused_closed_periods": 10,
                "first_created": 599, "injected_failed_periods": 1, "retry_created": 1, "replay_created": 0,
                "final_distinct_periods": 610, "initial_batches": len(first), "retry_batches": len(retry),
                "replay_batches": len(replay), "elapsed_seconds": round(perf_counter() - started, 2), "pass": True}
            output = Path(__file__).resolve().parents[2] / "test-results/large-billing-batch.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        finally:
            # Only this committed fixture's run chain; financial teardown remains
            # in committed_case and never targets the development database.
            with Session(test_engine) as db:
                run_ids = list(db.scalars(select(BillingRun.id).where(BillingRun.requested_by == ids["actor"])))
                db.execute(delete(BillingOutcome).where(BillingOutcome.run_id.in_(run_ids)))
                db.execute(update(BillingRun).where(BillingRun.id.in_(run_ids)).values(retry_of_id=None))
                db.execute(delete(BillingRun).where(BillingRun.id.in_(run_ids)))
                db.commit()
