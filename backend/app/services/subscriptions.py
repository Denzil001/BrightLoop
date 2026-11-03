"""Subscription aggregate commands; callers own the database transaction."""
import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import get_business_now, get_business_today
from app.models.catalog import Plan, PlanItem, Product, ProductVariant
from app.models.customers import Customer
from app.models.subscriptions import (
    AgreementDiscount, AgreementLine, AgreementLineTax, AgreementVersion,
    Subscription, SubscriptionEvent, SubscriptionTerm,
)
from app.models.taxes import PlanTax, ProductTax, TaxRule
from app.models.templates import QuotationTemplate
from app.models.users import CommandReceipt
from app.schemas.pricing import PricingLineInput, PricingPreviewRequest
from app.services.pricing import PricingError, PricingService
from app.services.template_validation import validate_active_template

POLICIES = ("allow_pause", "allow_resume", "allow_renewal", "allow_early_closure", "auto_close_on_expiry")


def fail(message, code=409):
    raise HTTPException(code, message)


def load_subscription(db, subscription_id, user, lock=False):
    query = select(Subscription).where(Subscription.id == subscription_id)
    if user.role == "CUSTOMER":
        query = query.join(Customer).where(Customer.user_id == user.id)
    if lock:
        query = query.with_for_update(of=Subscription)
    subscription = db.scalar(query)
    if subscription is None:
        fail("Subscription not found.", 404)
    return subscription


def snapshot_draft(db: Session, subscription, payload, sequence):
    """Build a complete version without modifying any issued/accepted version."""
    plan = db.get(Plan, payload.plan_id)
    if not plan or not plan.active:
        fail("Select an active plan.", 422)
    if not db.get(Customer, payload.customer_id):
        fail("Customer not found.", 404)
    template = None
    lines = payload.lines
    if payload.template_id:
        template = db.get(QuotationTemplate, payload.template_id)
        if not template or not template.active or template.plan_id != plan.id:
            fail("Select an active template belonging to this plan.", 422)
        validate_active_template(db, plan.id, template.lines)
        if lines is None:
            lines = [PricingLineInput(product_id=x.product_id, variant_id=x.variant_id,
                                      quantity=x.quantity, line_kind=x.line_kind)
                     for x in sorted(template.lines, key=lambda x: x.ordinal)]
    if lines is None:
        lines = [PricingLineInput(product_id=x.product_id, variant_id=x.variant_id,
                                  quantity=x.included_quantity, line_kind="INCLUDED")
                 for x in db.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id).order_by(PlanItem.ordinal))]
    try:
        pricing = PricingService.calculate_pricing(db, PricingPreviewRequest(
            plan_id=plan.id, seat_quantity=payload.seat_quantity, lines=lines,
            discount_id=payload.discount_id, discount_ids=payload.discount_ids, as_of_date=payload.start_date))
    except PricingError as exc:
        fail(str(exc), 422)
    version = AgreementVersion(
        subscription_id=subscription.id, sequence=sequence, state="DRAFT",
        template_id=template.id if template else None, seat_quantity=payload.seat_quantity,
        proposed_start_date=payload.start_date, proposed_expiry_date=payload.expiry_date,
        proposed_interval=plan.interval, payment_term_days=payload.payment_term_days
        if payload.payment_term_days is not None else plan.payment_term_days,
        currency="INR", policy_snapshot={key: getattr(plan, key) for key in POLICIES},
        pricing_snapshot=pricing.model_dump(mode="json"),
        validity_days=payload.validity_days if payload.validity_days is not None else (template.validity_days if template else 30),
    )
    db.add(version)
    db.flush()
    input_lines = iter(lines)
    for item in pricing.lines:
        source = next(input_lines) if item.product_id else None
        product = db.get(Product, item.product_id) if item.product_id else None
        variant = db.get(ProductVariant, item.variant_id) if item.variant_id else None
        line = AgreementLine(version_id=version.id, ordinal=item.ordinal, kind=item.line_kind,
                             product_id=item.product_id, variant_id=item.variant_id,
                             snapshot_name=product.name if product else item.description,
                             snapshot_type=product.type if product else None,
                             snapshot_variant_name=variant.name if variant else None,
                             quantity=item.quantity, unit_price=Decimal(item.unit_price),
                             override_reason=source.override_reason if source else None)
        db.add(line)
        db.flush()
        if item.line_kind == "INCLUDED":
            continue
        association = ProductTax if product else PlanTax
        owner_field = association.product_id if product else association.plan_id
        taxes = db.scalars(select(TaxRule).join(association, association.tax_rule_id == TaxRule.id)
                           .where(owner_field == (product.id if product else plan.id), TaxRule.active.is_(True)))
        for tax in taxes:
            db.add(AgreementLineTax(line_id=line.id, source_tax_id=tax.id, snapshot_name=tax.name,
                                   snapshot_classification=tax.classification, snapshot_rate=tax.rate))
    # Pin the assigned revision even if today's preview is ineligible. Eligibility is
    # evaluated again for each actual period; previews reserve no redemption.
    for revision_id in pricing.assigned_discount_revision_ids:
        db.add(AgreementDiscount(version_id=version.id, revision_id=revision_id))
    db.flush()
    return version


def create_draft(db, payload, actor):
    subscription = Subscription(number=f"SUB-{uuid.uuid4().hex.upper()}", customer_id=payload.customer_id,
                                plan_id=payload.plan_id, creator_id=actor.id, state="DRAFT",
                                seat_quantity=payload.seat_quantity)
    db.add(subscription)
    db.flush()
    snapshot_draft(db, subscription, payload, 1)
    return subscription


def replace_draft(db, subscription, payload):
    if subscription.version != payload.expected_version:
        fail("This subscription changed. Refresh before saving.")
    if subscription.state not in ("DRAFT", "QUOTATION"):
        fail("Only draft subscriptions and unaccepted quotations can be edited.")
    if subscription.state == "QUOTATION" and (payload.customer_id != subscription.customer_id or payload.plan_id != subscription.plan_id):
        fail("An issued subscription must retain its customer and plan. Prepare a separate draft for a different sale.", 422)
    versions = db.scalars(select(AgreementVersion).where(AgreementVersion.subscription_id == subscription.id)
                          .order_by(AgreementVersion.sequence)).all()
    sequence = max(v.sequence for v in versions) + 1
    for version in versions:
        if version.state == "DRAFT":
            db.delete(version)
    db.flush()
    snapshot_draft(db, subscription, payload, sequence)
    subscription.customer_id = payload.customer_id
    subscription.plan_id = payload.plan_id
    subscription.seat_quantity = payload.seat_quantity
    subscription.version += 1
    return subscription


def execute_command(db, subscription, command, actor):
    operation = f"subscription:{subscription.id}"
    request_hash = hashlib.sha256(command.model_dump_json().encode()).hexdigest()
    receipt = db.scalar(select(CommandReceipt).where(CommandReceipt.actor_id == actor.id,
                        CommandReceipt.operation == operation, CommandReceipt.request_key == command.request_key))
    if receipt:
        if receipt.request_hash != request_hash:
            fail("This request key was already used for a different command.")
        return subscription
    if subscription.version != command.expected_version:
        fail("This subscription changed. Refresh before continuing.")
    today = get_business_today()
    versions = db.scalars(select(AgreementVersion).where(AgreementVersion.subscription_id == subscription.id)
                          .order_by(AgreementVersion.sequence.desc())).all()
    version = next((v for v in versions if v.id == command.agreement_id), None) if command.agreement_id else versions[0]
    if not version:
        fail("Agreement version not found.", 404)
    action = command.action
    if action == "ISSUE":
        if subscription.state not in ("DRAFT", "QUOTATION") or version.state != "DRAFT":
            fail("Only a draft commercial version can be issued.")
        for older in versions:
            if older.state == "ISSUED":
                older.state = "SUPERSEDED"
        version.state = "ISSUED"
        version.issued_date = today
        version.valid_until = today + timedelta(days=version.validity_days)
        version.quote_number = f"QUO-{uuid.uuid4().hex.upper()}"
        subscription.state = "QUOTATION"
    elif action == "CONFIRM":
        if subscription.state != "QUOTATION" or version.state != "ISSUED":
            fail("Only the current issued quotation can be confirmed.")
        if version.valid_until < today:
            fail("This quotation has expired. Issue a revised quotation.")
        if any(v.state == "DRAFT" for v in versions):
            fail("An unsent revision exists. Issue or discard it before confirmation.")
        plan = db.get(Plan, subscription.plan_id)
        if not plan.active or (plan.available_from and version.proposed_start_date < plan.available_from) or (plan.available_to and version.proposed_start_date > plan.available_to):
            fail("This plan is no longer available for the proposed start date.")
        term = SubscriptionTerm(subscription_id=subscription.id, sequence=1,
                                start_date=version.proposed_start_date, expiry_date=version.proposed_expiry_date,
                                original_anchor_date=version.proposed_start_date, interval=version.proposed_interval,
                                source_version_id=version.id, **version.policy_snapshot)
        db.add(term)
        db.flush()
        version.term_id = term.id
        version.state = "ACCEPTED"
        version.accepted_at = get_business_now()
        version.effective_from = term.start_date
        subscription.state = "CONFIRMED"
    elif action == "ACTIVATE":
        if subscription.state != "CONFIRMED" or version.state != "ACCEPTED":
            fail("Only a confirmed subscription can be activated.")
        if today < version.proposed_start_date:
            fail("Service cannot activate before its start date.")
        subscription.state = "ACTIVE"
        subscription.next_billing_date = version.proposed_start_date
    elif action == "ABANDON":
        if subscription.state not in ("DRAFT", "QUOTATION") or not command.reason or not command.reason.strip():
            fail("Only unaccepted subscriptions can be abandoned, with a reason.")
        subscription.state = "CLOSED"
    subscription.version += 1
    db.add(SubscriptionEvent(subscription_id=subscription.id, action=action, effective_date=today,
                             agreement_id=version.id, actor_id=actor.id, applied_at=get_business_now(),
                             payload={"reason": command.reason} if command.reason else None))
    db.add(CommandReceipt(actor_id=actor.id, operation=operation, request_key=command.request_key,
                          request_hash=request_hash, result_type="subscription", result_id=str(subscription.id)))
    db.flush()
    return subscription
