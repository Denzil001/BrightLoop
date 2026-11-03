"""Authorized subscription reads and transactional aggregate commands."""
import uuid
import hashlib
import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.contracts import created_location, ordering
from app.api.deps import get_current_db, get_current_user, require_role, verify_csrf, verify_origin
from app.models.customers import Customer
from app.models.catalog import Plan, Product
from app.models.subscriptions import AgreementVersion, Subscription, SubscriptionRequest, SubscriptionTerm
from app.models.users import CommandReceipt, User
from app.models.invoices import Invoice
from app.schemas.subscriptions import (ChangeRequestCreate, ChangeRequestReview, DraftUpdate,
                                      LifecycleCommand, LifecycleIntent, SubscriptionCommand, SubscriptionDraft)
from app.services import subscriptions as service
from app.services import change_requests, lifecycle
from app.services.reporting import active_service
from app.core.datetime_utils import get_business_today

router = APIRouter()
mutation = [Depends(verify_origin), Depends(verify_csrf)]


def summary(subscription):
    return {"id": subscription.id, "number": subscription.number, "customer_id": subscription.customer_id,
            "customer_name": subscription.customer.name, "plan_id": subscription.plan_id,
            "plan_name": subscription.plan.name, "state": subscription.state,
            "seat_quantity": subscription.seat_quantity, "version": subscription.version,
            "next_billing_date": subscription.next_billing_date}


def detail(db, subscription, user):
    result = summary(subscription)
    versions = db.scalars(select(AgreementVersion).where(AgreementVersion.subscription_id == subscription.id)
                          .order_by(AgreementVersion.sequence.desc())).all()
    result["agreements"] = []
    for version in versions:
        lines = []
        for line in sorted(version.lines, key=lambda x: x.ordinal):
            estimate = next((item for item in (version.pricing_snapshot or {}).get("lines", [])
                if item.get("ordinal") == line.ordinal), {})
            item = {"id": line.id, "ordinal": line.ordinal, "kind": line.kind, "name": line.snapshot_name,
                    "variant_name": line.snapshot_variant_name, "product_id": line.product_id,
                    "variant_id": line.variant_id, "quantity": line.quantity,
                    "unit_price": str(line.unit_price), "subtotal": str(line.unit_price * line.quantity),
                    "discount_amount": estimate.get("discount_amount"), "tax_amount": estimate.get("tax_amount"),
                    "total": estimate.get("total"),
                    "taxes": [{"name": tax.snapshot_name, "rate": str(tax.snapshot_rate)} for tax in line.taxes]}
            if user.role != "CUSTOMER":
                item["override_reason"] = line.override_reason
            lines.append(item)
        result["agreements"].append({"id": version.id, "sequence": version.sequence,
            "state": version.state, "quote_number": version.quote_number, "issued_date": version.issued_date,
            "valid_until": version.valid_until, "start_date": version.proposed_start_date,
            "effective_from": version.effective_from,
            "pending_change": any(event.agreement_id == version.id and event.applied_at is None for event in subscription.events),
            "expiry_date": version.proposed_expiry_date, "interval": version.proposed_interval,
            "payment_term_days": version.payment_term_days, "seat_quantity": version.seat_quantity,
            "currency": version.currency, "policies": version.policy_snapshot, "lines": lines,
            "pricing_estimate": version.pricing_snapshot,
            "discount_revision_ids": [d.revision_id for d in version.discounts],
            "discount_rule_ids": [d.revision.rule_id for d in version.discounts]})
    result["terms"] = [{"id": t.id, "sequence": t.sequence, "start_date": t.start_date,
                        "expiry_date": t.expiry_date, "interval": t.interval,
                        "policies": {key: getattr(t, key) for key in service.POLICIES}} for t in sorted(subscription.terms, key=lambda x: x.sequence)]
    result["events"] = [{"id": event.id, "action": event.action, "effective_date": event.effective_date,
                         "applied_at": event.applied_at} for event in sorted(subscription.events, key=lambda x: x.created_at)]
    result["requests"] = [{"id": request.id, "action": request.type, "effective_date": request.requested_date,
                            "status": request.status, "note": (request.desired_items or {}).get("reason"),
                            "review_reason": request.reason if request.status != "PENDING" else None,
                            "reviewed_at": request.reviewed_at,
                            "reviewer_name": request.reviewer.name if request.reviewer else None,
                            "proposal": (request.desired_items or {}).get("proposal"),
                            "price_summary": request.displayed_price_summary}
                           for request in sorted(subscription.requests, key=lambda x: x.created_at, reverse=True)]
    invoices = select(Invoice).where(Invoice.subscription_id == subscription.id)
    if user.role == "CUSTOMER":
        invoices = invoices.where(Invoice.issued_at.is_not(None))
    result["invoices"] = [{"id": invoice.id, "number": invoice.number, "state": invoice.state,
                           "period_start": invoice.period_start, "total": str(invoice.total)}
                          for invoice in db.scalars(invoices.order_by(Invoice.period_start.desc(), Invoice.id).limit(20))]
    return result


@router.get("")
def list_subscriptions(search: str | None = Query(None, max_length=200), state: str | None = Query(None, pattern="^(|DRAFT|QUOTATION|CONFIRMED|ACTIVE|PAUSED|CLOSED|ENDED)$"),
                       plan_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None,
                       pending_requests: bool = False, billing_before: date | None = None,
                       service_active: bool = False,
                       expiry_before: date | None = None, plan_search: str = Query("", max_length=200),
                       sort: str = Query("created_at", pattern="^(created_at|number|next_billing_date|expiry_date)$"), descending: bool = True,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    query = select(Subscription).join(Customer)
    term_expiry = select(SubscriptionTerm.expiry_date).where(SubscriptionTerm.subscription_id == Subscription.id).order_by(SubscriptionTerm.sequence.desc()).limit(1).correlate(Subscription).scalar_subquery()
    proposed_expiry = select(AgreementVersion.proposed_expiry_date).where(AgreementVersion.subscription_id == Subscription.id).order_by(AgreementVersion.sequence.desc()).limit(1).correlate(Subscription).scalar_subquery()
    expiry = func.coalesce(term_expiry, proposed_expiry)
    if user.role == "CUSTOMER":
        query = query.where(Customer.user_id == user.id)
    if search:
        pattern = f"%{search.strip()}%"
        quote_match = exists().where(AgreementVersion.subscription_id == Subscription.id,
                                     AgreementVersion.quote_number.ilike(pattern))
        query = query.where(Subscription.number.ilike(pattern) | Customer.name.ilike(pattern) | quote_match)
    if state == "ENDED":
        query = query.where(expiry <= get_business_today(), Subscription.state.in_(["ACTIVE", "CLOSED"]))
    elif state:
        query = query.where(Subscription.state == state)
    if service_active:
        query = query.where(active_service())
    if plan_id:
        query = query.where(Subscription.plan_id == plan_id)
    if customer_id:
        query = query.where(Subscription.customer_id == customer_id)
    if billing_before:
        query = query.where(Subscription.next_billing_date <= billing_before)
    if expiry_before:
        query = query.where(expiry <= expiry_before)
    if plan_search:
        query = query.join(Plan).where(Plan.name.ilike(f"%{plan_search}%"))
    if pending_requests:
        query = query.where(exists().where(SubscriptionRequest.subscription_id == Subscription.id,
                                          SubscriptionRequest.status == "PENDING"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    recurring = select(AgreementVersion.pricing_snapshot["total"].astext).where(
        AgreementVersion.subscription_id == Subscription.id,
        or_(AgreementVersion.state != "ACCEPTED", AgreementVersion.effective_from <= get_business_today()))
    recurring = recurring.order_by(case((AgreementVersion.state == "ACCEPTED", 0), else_=1), AgreementVersion.sequence.desc()).limit(1).correlate(Subscription).scalar_subquery()
    pending_count = select(func.count(SubscriptionRequest.id)).where(SubscriptionRequest.subscription_id == Subscription.id,
        SubscriptionRequest.status == "PENDING").correlate(Subscription).scalar_subquery()
    items = db.execute(query.add_columns(recurring.label("recurring_amount"), expiry.label("expiry_date"), pending_count.label("request_count"))
                       .options(selectinload(Subscription.customer), selectinload(Subscription.plan))
                       .order_by(*ordering(sort, descending, {"created_at": Subscription.created_at, "number": Subscription.number, "next_billing_date": Subscription.next_billing_date, "expiry_date": expiry}, Subscription.id))
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{**summary(item), "recurring_amount": amount, "expiry_date": expires, "request_count": count,
                       "ended": bool(expires and expires <= get_business_today() and item.state in ("ACTIVE", "CLOSED"))}
                       for item, amount, expires, count in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201, dependencies=mutation)
def create_subscription(response: Response, payload: SubscriptionDraft, issue: bool = False,
                         idempotency_key: str | None = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
                         db: Session = Depends(get_current_db),
                         user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    digest = hashlib.sha256(json.dumps({"payload": payload.model_dump(mode="json"), "issue": issue},
                                      sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if idempotency_key:
        if not idempotency_key.strip():
            service.fail("Provide a non-empty draft creation key.", 422)
        # Serialize creation retries for this actor before testing the scoped key.
        # This transaction creates a new aggregate, so it never waits on an older
        # subscription lock while holding this actor lock.
        db.scalar(select(User.id).where(User.id == user.id).with_for_update())
        receipt = db.scalar(select(CommandReceipt).where(CommandReceipt.actor_id == user.id,
            CommandReceipt.operation == "subscription-create", CommandReceipt.request_key == idempotency_key))
        if receipt:
            if receipt.request_hash != digest:
                service.fail("A subscription was already created from this save attempt. Retry with the original details or open it from the subscriptions list.")
            created_location(response, f"subscriptions/{receipt.result_id}")
            return detail(db, service.load_subscription(db, uuid.UUID(receipt.result_id), user), user)
    subscription = service.create_draft(db, payload, user)
    if issue:
        service.execute_command(db, subscription, SubscriptionCommand(expected_version=subscription.version,
                                request_key=uuid.uuid4().hex, action="ISSUE"), user)
    if idempotency_key:
        db.add(CommandReceipt(actor_id=user.id, operation="subscription-create", request_key=idempotency_key,
            request_hash=digest, result_type="subscription", result_id=str(subscription.id)))
    db.commit()
    created_location(response, f"subscriptions/{subscription.id}")
    return detail(db, subscription, user)


@router.get("/{subscription_id}")
def get_subscription(subscription_id: uuid.UUID, db: Session = Depends(get_current_db),
                     user: User = Depends(get_current_user)):
    return detail(db, service.load_subscription(db, subscription_id, user), user)


@router.patch("/{subscription_id}", dependencies=mutation)
def update_subscription(subscription_id: uuid.UUID, payload: DraftUpdate, db: Session = Depends(get_current_db),
                        user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    service.replace_draft(db, subscription, payload)
    db.commit()
    db.expire_all()
    return detail(db, subscription, user)


@router.post("/{subscription_id}/commands", dependencies=mutation)
def command_subscription(subscription_id: uuid.UUID, payload: SubscriptionCommand,
                         db: Session = Depends(get_current_db),
                         user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    service.execute_command(db, subscription, payload, user)
    db.commit()
    return detail(db, subscription, user)


@router.post("/{subscription_id}/lifecycle", dependencies=mutation)
def schedule_lifecycle(subscription_id: uuid.UUID, payload: LifecycleCommand,
                        db: Session = Depends(get_current_db),
                        user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    operation = f"lifecycle:{subscription.id}"
    receipt, digest = change_requests.lookup_receipt(db, user, operation, payload)
    if not receipt:
        if payload.expected_version != subscription.version:
            service.fail("The subscription changed. Refresh before continuing.")
        change_requests.price_intent(db, payload)
        lifecycle.schedule_intent(db, subscription, payload, user)
        change_requests.record_receipt(db, user, operation, payload, digest, subscription)
        db.commit()
    return detail(db, subscription, user)


@router.post("/{subscription_id}/requests", status_code=201, dependencies=mutation)
def submit_change_request(response: Response, subscription_id: uuid.UUID, payload: ChangeRequestCreate,
                           db: Session = Depends(get_current_db),
                           user: User = Depends(require_role(["CUSTOMER"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    change_requests.submit_request(db, subscription, payload, user)
    db.commit()
    created_location(response, f"subscriptions/{subscription.id}")
    return detail(db, subscription, user)


def load_request(db, subscription, request_id):
    request = db.scalar(select(SubscriptionRequest).where(SubscriptionRequest.id == request_id,
                        SubscriptionRequest.subscription_id == subscription.id).with_for_update())
    if not request:
        service.fail("Change request not found.", 404)
    return request


@router.post("/{subscription_id}/requests/{request_id}/cancel", dependencies=mutation)
def cancel_change_request(subscription_id: uuid.UUID, request_id: uuid.UUID,
                           db: Session = Depends(get_current_db),
                           user: User = Depends(require_role(["CUSTOMER"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    request = load_request(db, subscription, request_id)
    if request.requested_by != user.id:
        service.fail("Change request not found.", 404)
    if request.status != "PENDING":
        service.fail("Only pending requests can be cancelled.")
    request.status = "CANCELLED"
    db.commit()
    return detail(db, subscription, user)


@router.post("/{subscription_id}/requests/{request_id}/review", dependencies=mutation)
def review_change_request(subscription_id: uuid.UUID, request_id: uuid.UUID, payload: ChangeRequestReview,
                           db: Session = Depends(get_current_db),
                           user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    subscription = service.load_subscription(db, subscription_id, user, lock=True)
    request = load_request(db, subscription, request_id)
    change_requests.review_request(db, subscription, request, payload, user)
    db.commit()
    return detail(db, subscription, user)


@router.get("/{subscription_id}/change-options")
def change_options(subscription_id: uuid.UUID, search: str = Query("", max_length=200),
                    product_id: uuid.UUID | None = None,
                    db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    subscription = service.load_subscription(db, subscription_id, user)
    plan = db.get(Plan, subscription.plan_id)
    products = db.scalars(select(Product).where(Product.active.is_(True),
                          Product.id == product_id if product_id else Product.name.ilike(f"%{search}%"))
                          .options(selectinload(Product.variants)).order_by(Product.name, Product.id).limit(100)).all()
    return {"plans": [{"id": plan.id, "name": plan.name, "minimum_seats": plan.minimum_seats,
                       "base_fee": str(plan.base_fee), "extra_seat_unit_price": str(plan.extra_seat_unit_price),
                       "payment_term_days": plan.payment_term_days, "interval": plan.interval, "items": [],
                       **{key: getattr(plan, key) for key in service.POLICIES}}],
            "products": [{"id": product.id, "name": product.name, "sales_price": str(product.sales_price),
                          "variants": [{"id": v.id, "name": v.name, "active": v.active,
                                        "effective_sales_price": str(product.sales_price + v.price_adjustment)}
                                       for v in product.variants if v.active]} for product in products]}


@router.post("/{subscription_id}/change-preview", dependencies=mutation)
def change_preview(subscription_id: uuid.UUID, payload: LifecycleIntent,
                    db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    subscription = service.load_subscription(db, subscription_id, user)
    lifecycle.validate_intent(db, subscription, payload)
    return change_requests.price_intent(db, payload)
