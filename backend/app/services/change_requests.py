"""Request review never silently substitutes changed commercial terms."""
import hashlib

from sqlalchemy import select

from app.core.datetime_utils import get_business_now
from app.models.subscriptions import SubscriptionRequest
from app.models.users import CommandReceipt
from app.models.catalog import Plan
from app.schemas.pricing import PricingPreviewRequest
from app.schemas.subscriptions import LifecycleIntent
from app.services.lifecycle import schedule_intent, validate_intent
from app.services.pricing import PricingError, PricingService
from app.services.subscriptions import POLICIES, fail


def lookup_receipt(db, actor, operation, payload):
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    receipt = db.scalar(select(CommandReceipt).where(CommandReceipt.actor_id == actor.id,
                        CommandReceipt.operation == operation, CommandReceipt.request_key == payload.request_key))
    if receipt and receipt.request_hash != digest:
        fail("This request key has already been used for different terms.")
    return receipt, digest


def record_receipt(db, actor, operation, payload, digest, subscription, result_type="subscription"):
    db.add(CommandReceipt(actor_id=actor.id, operation=operation, request_key=payload.request_key,
                          request_hash=digest, result_type=result_type, result_id=str(subscription.id)))


def price_intent(db, intent):
    if not intent.proposal:
        return None
    p = intent.proposal
    # Explicit line sets make customer review unambiguous; implicit template/default
    # population belongs to the operational quote editor.
    if p.lines is None or p.template_id:
        fail("Supply the complete proposed line set for a commercial change.", 422)
    try:
        result = PricingService.calculate_pricing(db, PricingPreviewRequest(plan_id=p.plan_id,
            seat_quantity=p.seat_quantity, lines=p.lines, discount_id=p.discount_id, discount_ids=p.discount_ids,
            as_of_date=p.start_date)).model_dump(mode="json")
        plan = db.get(Plan, p.plan_id)
        result["plan_policies"] = {key: getattr(plan, key) for key in POLICIES}
        result["billing_interval"] = plan.interval
        return result
    except PricingError as exc:
        fail(str(exc), 422)


def submit_request(db, subscription, payload, actor):
    if payload.action == "EARLY_CLOSE":
        fail("Early closure is an operational action; contact the team.", 403)
    if payload.expected_version != subscription.version:
        fail("This subscription changed. Review the current terms before requesting a change.")
    validate_intent(db, subscription, payload)
    existing = db.scalar(select(SubscriptionRequest.id).where(SubscriptionRequest.subscription_id == subscription.id,
                         SubscriptionRequest.status == "PENDING", SubscriptionRequest.type == payload.action).limit(1))
    if existing:
        fail("A pending request for this action already exists.")
    request = SubscriptionRequest(subscription_id=subscription.id, requested_by=actor.id,
        type=payload.action, requested_date=payload.effective_date,
        desired_items=LifecycleIntent.model_validate(payload.model_dump(exclude={"expected_version"})).model_dump(mode="json"),
        displayed_price_summary=price_intent(db, payload), based_on_version=subscription.version,
        status="PENDING", reason=payload.reason)
    db.add(request)
    db.flush()
    return request


def review_request(db, subscription, request, payload, actor):
    operation = f"request:{request.id}"
    receipt, digest = lookup_receipt(db, actor, operation, payload)
    if receipt:
        return
    if request.status != "PENDING":
        fail("Only pending requests can be reviewed.")
    if payload.expected_version != subscription.version:
        fail("The subscription changed. Refresh before reviewing.")
    if not payload.reason.strip():
        fail("Give the customer a review reason.", 422)
    if payload.decision == "APPROVE":
        if request.based_on_version != subscription.version:
            fail("Requested terms are stale. Reject with an explanation and ask for a new request.")
        intent = LifecycleIntent.model_validate(request.desired_items)
        if price_intent(db, intent) != request.displayed_price_summary:
            fail("Pricing changed after submission. Reject and request customer review of the new terms.")
        schedule_intent(db, subscription, intent, actor, request.id)
        request.status = "APPROVED"
    else:
        request.status = "REJECTED"
    request.reviewer_id = actor.id
    request.reviewed_at = get_business_now()
    # Keep the submitted note in desired_items; reason records the review outcome.
    request.reason = payload.reason.strip()
    record_receipt(db, actor, operation, payload, digest, subscription)
    db.flush()
