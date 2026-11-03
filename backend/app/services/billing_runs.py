"""Bounded orchestration; each financial period commits independently."""
import uuid
from sqlalchemy import exists, select, text

from app.core.datetime_utils import get_business_now, get_business_today
from app.db.session import SessionLocal
from app.models.billing import BillingOutcome, BillingRun
from app.models.invoices import Invoice
from app.models.subscriptions import Subscription, SubscriptionEvent, SubscriptionTerm
from app.services.billing import BillingFailure, _first_unprocessed, process_next_period
from app.services.financial_calculator import PricingError


def has_due_work(db, subscription_id, as_of):
    pending = db.scalar(select(SubscriptionEvent.id).where(SubscriptionEvent.subscription_id == subscription_id,
        SubscriptionEvent.applied_at.is_(None), SubscriptionEvent.effective_date <= as_of).limit(1))
    if pending:
        return True
    existing = set(db.scalars(select(Invoice.period_start).where(Invoice.subscription_id == subscription_id)))
    candidate = _first_unprocessed(db, subscription_id, existing)
    return bool(candidate and candidate.start <= as_of)


def run_lock_key(run_id):
    return int.from_bytes(run_id.bytes[:8], "big", signed=True)


def run_billing(as_of, actor_id=None, trigger="MANUAL", after_subscription_id=None,
                max_periods=100, batch_size=100, session_factory=SessionLocal, subscription_id=None, retry_of_id=None):
    # Pin a separate connection so process death releases run ownership without
    # guessing from elapsed time. Recovery can distinguish a slow live run.
    run_id = uuid.uuid4()
    with session_factory() as db:
        bind = db.get_bind().engine
    with bind.connect() as owner:
        owner.execute(text("SELECT pg_advisory_lock(:key)"), {"key": run_lock_key(run_id)})
        owner.commit()
        try:
            return _run_billing(as_of, actor_id, trigger, after_subscription_id, max_periods, batch_size,
                session_factory, subscription_id, retry_of_id, run_id)
        finally:
            owner.rollback()
            owner.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": run_lock_key(run_id)})
            owner.commit()


def _run_billing(as_of, actor_id=None, trigger="MANUAL", after_subscription_id=None,
                max_periods=100, batch_size=100, session_factory=SessionLocal, subscription_id=None, retry_of_id=None, run_id=None):
    if as_of > get_business_today():
        raise PricingError("Future billing runs are not allowed.")
    if not 1 <= max_periods <= 100 or not 1 <= batch_size <= 100:
        raise PricingError("Each request may scan and bill at most 100 subscriptions/periods.")
    with session_factory() as db:
        if retry_of_id and db.get(BillingRun, retry_of_id) is None:
            raise PricingError("The preceding billing run was not found.")
        run = BillingRun(id=run_id, requested_by=actor_id, trigger=trigger, as_of_date=as_of, state="RUNNING", retry_of_id=retry_of_id,
            summary_counts={"target_subscription_id": str(subscription_id) if subscription_id else None,
                "has_more": True, "continue_after_id": str(after_subscription_id) if after_subscription_id else None})
        db.add(run)
        db.commit()
        run_id = run.id
        query = select(Subscription.id).where(exists().where(
            SubscriptionTerm.subscription_id == Subscription.id, SubscriptionTerm.start_date <= as_of))
        if subscription_id:
            query = query.where(Subscription.id == subscription_id)
        if after_subscription_id:
            query = query.where(Subscription.id > after_subscription_id)
        selected = list(db.scalars(query.order_by(Subscription.id).limit(batch_size + 1)))
    more_scan, targets = len(selected) > batch_size, selected[:batch_size]
    counts = {"created": 0, "existing": 0, "failed": 0, "subscriptions_scanned": 0,
              "has_more": more_scan, "continue_after_id": str(after_subscription_id) if after_subscription_id else None,
              "target_subscription_id": str(subscription_id) if subscription_id else None}
    completed_cursor = after_subscription_id
    for index, subscription_id in enumerate(targets):
        counts["subscriptions_scanned"] += 1
        failed = False
        created_for_subscription = 0
        while counts["created"] < max_periods:
            try:
                with session_factory() as db:
                    result = process_next_period(db, subscription_id, as_of, run_id, actor_id)
                    db.commit()
                if result.state == "CREATED":
                    counts["created"] += 1
                    created_for_subscription += 1
                else:
                    counts["existing"] += result.state == "EXISTING" and not created_for_subscription
                    break
            except Exception as exc:
                db.rollback()
                # The failed period transaction has closed/rolled back. Persist
                # diagnostics separately; SQL, parameters and tracebacks stay out.
                with session_factory() as db:
                    period_start = getattr(exc, "period_start", None)
                    if period_start is None:
                        existing = set(db.scalars(select(Invoice.period_start).where(Invoice.subscription_id == subscription_id)))
                        candidate = _first_unprocessed(db, subscription_id, existing)
                        period_start = candidate.start if candidate else as_of
                    code = exc.safe_code if isinstance(exc, BillingFailure) else "RECONCILIATION_FAILED"
                    db.add(BillingOutcome(run_id=run_id, subscription_id=subscription_id,
                        period_start=period_start, state="FAILED", safe_error_code=code))
                    db.commit()
                counts["failed"] += 1
                failed = True
                break  # failure blocks later periods on this subscription
        with session_factory() as db:
            unfinished = has_due_work(db, subscription_id, as_of)
        if not unfinished or failed:
            completed_cursor = subscription_id
        if counts["created"] >= max_periods:
            counts["has_more"] = unfinished or index + 1 < len(targets) or more_scan
            break
    counts["continue_after_id"] = str(completed_cursor) if counts["has_more"] and completed_cursor else None
    with session_factory() as db:
        run = db.get(BillingRun, run_id)
        run.state = "FAILED" if counts["failed"] else "COMPLETED"
        run.finished_at = get_business_now()
        run.summary_counts = counts
        db.commit()
    return run_id
