"""Separate worker; a pinned PostgreSQL connection owns the tick advisory lock.

Financial work still uses run_billing and its per-period transactions. The lock
prevents two workers scanning at once; invoice identities protect manual races.
"""
from datetime import timedelta
import uuid
from sqlalchemy import delete, func, select, text, update

from app.core.datetime_utils import get_business_now, get_business_today
from app.db.session import engine, SessionLocal
from app.models.billing import BillingOutcome, BillingRun, EmailAttempt
from app.models.scheduler import SchedulerState
from app.models.rate_limits import RateLimitWindow
from app.models.users import AuthChallenge
from app.services.billing_runs import run_billing, run_lock_key

LOCK_KEY = 731058204931


def scheduler_status(db):
    state = db.get(SchedulerState, 1)
    if state is None:
        return {"configured": False, "active": False, "message": "No scheduler worker has reported runtime status."}
    fresh = state.heartbeat_at >= get_business_now() - timedelta(seconds=max(120, state.interval_seconds * 2 + 30))
    active = fresh and state.state != "STOPPED"
    return {"configured": True, "active": active, "state": state.state if fresh else "STALE",
        "heartbeat_at": state.heartbeat_at, "finished_at": state.finished_at,
        "interval_seconds": state.interval_seconds, "last_run_id": state.last_run_id,
        "safe_error_code": state.safe_error_code,
        "message": (f"Worker {state.state.lower()}; interval {state.interval_seconds} seconds."
                    if active else "Worker is stopped or its heartbeat is stale; check the scheduler process.")}


def recover_interrupted(db):
    """Call only while owning the exclusive scheduler lock.

    Reconstruct committed outcomes rather than inventing success for work that
    may have crashed. SMTP acceptance is unknowable after connection/process loss.
    """
    for run in db.scalars(select(BillingRun).where(BillingRun.state == "RUNNING")):
        key = run_lock_key(run.id)
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
            continue  # A manual/CLI/scheduled caller still owns this run.
        counts = dict(db.execute(select(BillingOutcome.state, func.count()).where(
            BillingOutcome.run_id == run.id).group_by(BillingOutcome.state)).all())
        run.state, run.finished_at = "INTERRUPTED", get_business_now()
        run.summary_counts = {**(run.summary_counts or {}), "created": counts.get("CREATED", 0), "existing": counts.get("EXISTING", 0),
            "failed": counts.get("FAILED", 0), "has_more": True, "continue_after_id": None,
            "recovery_required": True}
    db.execute(update(EmailAttempt).where(EmailAttempt.status == "PENDING",
        EmailAttempt.attempted_at < get_business_now() - timedelta(minutes=15))
        .values(status="UNKNOWN", safe_error_code="DELIVERY_OUTCOME_UNKNOWN"))
    db.execute(delete(RateLimitWindow).where(RateLimitWindow.updated_at < get_business_now() - timedelta(days=1)))
    db.execute(delete(AuthChallenge).where(AuthChallenge.purpose == "PREAUTH_CSRF",
        AuthChallenge.expires_at < get_business_now() - timedelta(days=1)))
    db.commit()


def scheduler_tick(interval_seconds=60, max_batches=10, session_factory=SessionLocal,
                   lock_engine=engine, as_of=None, subscription_id=None):
    if not 10 <= interval_seconds <= 86400 or not 1 <= max_batches <= 100:
        raise ValueError("Use an interval of 10–86400 seconds and 1–100 batches per tick.")
    as_of = as_of or get_business_today()
    if as_of > get_business_today():
        raise ValueError("Future scheduler dates are not allowed.")
    with lock_engine.connect() as lock:
        acquired = lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY})
        lock.commit()
        if not acquired:
            return {"state": "SKIPPED", "reason": "ANOTHER_WORKER_ACTIVE", "batches": 0}
        try:
            with session_factory() as db:
                recover_interrupted(db)
                state = db.get(SchedulerState, 1)
                if state is None:
                    state = SchedulerState(id=1, interval_seconds=interval_seconds,
                        heartbeat_at=get_business_now(), state="RUNNING")
                    db.add(state)
                state.state, state.heartbeat_at = "RUNNING", get_business_now()
                state.interval_seconds, state.safe_error_code = interval_seconds, None
                cursor = None if subscription_id else state.continue_after_id
                previous = state.last_run_id
                db.commit()
            batches, failures, created = 0, 0, 0
            for _ in range(max_batches):
                # Probe the pinned connection before starting another batch.
                lock.execute(text("SELECT 1"))
                lock.commit()
                run_id = run_billing(as_of, trigger="SCHEDULED", after_subscription_id=cursor,
                    session_factory=session_factory, subscription_id=subscription_id, retry_of_id=previous)
                with session_factory() as db:
                    run = db.get(BillingRun, run_id)
                    summary = run.summary_counts
                    batches += 1
                    failures += summary["failed"]
                    created += summary["created"]
                    cursor = uuid.UUID(summary["continue_after_id"]) if summary["continue_after_id"] else None
                    state = db.get(SchedulerState, 1)
                    state.last_run_id, state.heartbeat_at = run_id, get_business_now()
                    if not subscription_id:
                        state.continue_after_id = cursor
                    db.commit()
                previous = run_id
                if not summary["has_more"]:
                    break
            with session_factory() as db:
                state = db.get(SchedulerState, 1)
                state.state = "FAILED" if failures else "IDLE"
                state.finished_at = state.heartbeat_at = get_business_now()
                state.safe_error_code = "BILLING_PERIODS_FAILED" if failures else None
                db.commit()
            return {"state": "FAILED" if failures else "COMPLETED", "batches": batches,
                "created": created, "failed": failures, "has_more": summary["has_more"], "last_run_id": str(run_id)}
        except Exception:
            with session_factory() as db:
                state = db.get(SchedulerState, 1)
                if state:
                    state.state, state.safe_error_code = "FAILED", "SCHEDULER_TICK_FAILED"
                    state.finished_at = state.heartbeat_at = get_business_now()
                    db.commit()
            raise
        finally:
            lock.rollback()
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            lock.commit()


def mark_worker_stopped(last_run_id, session_factory=SessionLocal, lock_engine=engine):
    """Do not overwrite a newer worker's status when this process exits."""
    if not last_run_id:
        return
    with lock_engine.connect() as lock:
        acquired = lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY})
        lock.commit()
        if not acquired:
            return
        try:
            with session_factory() as db:
                state = db.get(SchedulerState, 1)
                if state and str(state.last_run_id) == str(last_run_id):
                    state.state, state.heartbeat_at = "STOPPED", get_business_now()
                    db.commit()
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            lock.commit()
