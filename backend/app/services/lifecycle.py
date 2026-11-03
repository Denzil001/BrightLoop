"""Dated lifecycle events, separate from the financial billing cursor.

Approval records intent now. The shared event applier is used before each billing
boundary and by manual/scheduled lifecycle reconciliation.
"""
from datetime import timedelta

from sqlalchemy import select

from app.core.datetime_utils import get_business_now, get_business_today
from app.models.subscriptions import AgreementVersion, SubscriptionEvent, SubscriptionPause, SubscriptionTerm
from app.services.calendar import is_boundary
from app.services.subscriptions import POLICIES, fail, snapshot_draft


def latest_term(db, subscription):
    term = db.scalar(select(SubscriptionTerm).where(SubscriptionTerm.subscription_id == subscription.id)
                     .order_by(SubscriptionTerm.sequence.desc()).limit(1))
    if term is None:
        fail("This subscription has no accepted service term.")
    return term


def validate_intent(db, subscription, intent):
    today = get_business_today()
    term = latest_term(db, subscription)
    action, effective = intent.action, intent.effective_date
    if db.scalar(select(SubscriptionEvent.id).where(SubscriptionEvent.subscription_id == subscription.id,
                 SubscriptionEvent.applied_at.is_(None)).limit(1)):
        fail("A scheduled change is already pending. Apply it before scheduling another change.")
    if action == "RESUME":
        if subscription.state != "PAUSED" or not term.allow_resume:
            fail("This term cannot be resumed.")
        pause = db.scalar(select(SubscriptionPause).where(SubscriptionPause.term_id == term.id,
                                                         SubscriptionPause.resumed_date.is_(None)))
        if not pause or effective <= pause.start_date or effective < today:
            fail("Resume must be after the pause date and cannot be backdated.", 422)
    elif action == "RENEW":
        if not term.allow_renewal or subscription.state not in ("ACTIVE", "CLOSED"):
            fail("This term cannot be renewed.")
        if effective < term.expiry_date or effective < today:
            fail("Renewal cannot overlap the prior term or begin in the past.", 422)
        if today < term.expiry_date and effective != term.expiry_date:
            fail("A continuous renewal begins at the prior term's expiry.", 422)
    else:
        if subscription.state != "ACTIVE":
            fail("This action requires active service.")
        if action == "PAUSE" and not term.allow_pause:
            fail("The accepted plan does not permit pausing.")
        if action == "EARLY_CLOSE" and not term.allow_early_closure:
            fail("The accepted plan does not permit early closure.")
        if effective <= today:
            fail("Approve this change before its future billing boundary; due periods must be reconciled first.", 422)
        if effective >= term.expiry_date or not is_boundary(term.original_anchor_date, term.interval, effective):
            fail("Choose a billing boundary inside the current service term.", 422)
        if subscription.next_billing_date and effective < subscription.next_billing_date:
            fail("This boundary is already billed. Choose an unbilled boundary.", 422)
    if intent.proposal:
        p = intent.proposal
        if p.customer_id != subscription.customer_id or p.plan_id != subscription.plan_id:
            fail("A change must retain the subscription's customer and plan.", 422)
        if p.start_date != effective:
            fail("Commercial terms must start on the requested effective date.", 422)
        if action == "ADDON_CHANGE" and p.expiry_date != term.expiry_date:
            fail("An add-on change cannot change the term expiry.", 422)
    return term


def schedule_intent(db, subscription, intent, actor, request_id=None):
    term = validate_intent(db, subscription, intent)
    agreement = None
    if intent.proposal:
        sequence = db.scalar(select(AgreementVersion.sequence).where(AgreementVersion.subscription_id == subscription.id)
                             .order_by(AgreementVersion.sequence.desc()).limit(1)) + 1
        agreement = snapshot_draft(db, subscription, intent.proposal, sequence)
        if intent.action == "ADDON_CHANGE" and agreement.proposed_interval != term.interval:
            fail("An add-on change cannot change the billing interval. Review the plan and prepare a renewal instead.", 422)
        if intent.action == "ADDON_CHANGE":
            agreement.policy_snapshot = {key: getattr(term, key) for key in POLICIES}
        agreement.state = "ACCEPTED"
        agreement.accepted_at = get_business_now()
        agreement.effective_from = intent.effective_date
        agreement.term_id = term.id if intent.action == "ADDON_CHANGE" else None
    event = SubscriptionEvent(subscription_id=subscription.id, term_id=term.id, action=intent.action,
                              effective_date=intent.effective_date, actor_id=actor.id, request_id=request_id,
                              agreement_id=agreement.id if agreement else None, payload={"reason": intent.reason})
    db.add(event)
    subscription.version += 1
    db.flush()
    return event


def apply_event(db, subscription, event, as_of=None):
    """Caller locks the subscription and reconciles earlier periods first.

    A pending event at a future boundary is never applied early. The billing
    engine supplies boundaries chronologically, preserving pre-pause backlog.
    """
    if event.applied_at:
        return
    if event.effective_date > (as_of or get_business_today()):
        fail("A scheduled change cannot be applied before its effective date.")
    term = db.get(SubscriptionTerm, event.term_id)
    if event.action == "PAUSE":
        db.add(SubscriptionPause(term_id=term.id, start_date=event.effective_date,
                                original_expiry_date=term.expiry_date, pause_event_id=event.id))
        subscription.state = "PAUSED"
        subscription.next_billing_date = None
    elif event.action == "RESUME":
        pause = db.scalar(select(SubscriptionPause).where(SubscriptionPause.term_id == term.id,
                                                         SubscriptionPause.resumed_date.is_(None)))
        if pause is None:
            fail("No open pause exists for this term.")
        pause.resumed_date = event.effective_date
        pause.resume_event_id = event.id
        term.expiry_date += timedelta(days=(event.effective_date - pause.start_date).days)
        # original_anchor_date is this term's current service-segment anchor;
        # previous segments remain reconstructible from term start + pause history.
        term.original_anchor_date = event.effective_date
        subscription.next_billing_date = event.effective_date
        subscription.state = "ACTIVE"
    elif event.action == "EARLY_CLOSE":
        term.expiry_date = event.effective_date
        subscription.state = "CLOSED"
        subscription.next_billing_date = None
    elif event.action == "ADDON_CHANGE":
        agreement = db.get(AgreementVersion, event.agreement_id)
        subscription.seat_quantity = agreement.seat_quantity
    elif event.action == "RENEW":
        agreement = db.get(AgreementVersion, event.agreement_id)
        new_term = SubscriptionTerm(subscription_id=subscription.id, sequence=term.sequence + 1,
            start_date=event.effective_date, expiry_date=agreement.proposed_expiry_date,
            original_anchor_date=event.effective_date, interval=agreement.proposed_interval,
            source_version_id=agreement.id, **agreement.policy_snapshot)
        db.add(new_term)
        db.flush()
        agreement.term_id = new_term.id
        subscription.seat_quantity = agreement.seat_quantity
        subscription.state = "ACTIVE"
        subscription.next_billing_date = event.effective_date
    event.applied_at = get_business_now()
    subscription.version += 1
    db.flush()
