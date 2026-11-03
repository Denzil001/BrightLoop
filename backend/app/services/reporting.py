"""SQL-backed metrics and drill-downs. Receipts are ranged; balances are current."""
from datetime import timedelta
from decimal import Decimal
from time import perf_counter

from sqlalchemy import and_, case, exists, func, select, true

from app.core.datetime_utils import get_business_today
from app.db.querying import ordering
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.models.subscriptions import Subscription, SubscriptionEvent, SubscriptionPause, SubscriptionRequest, SubscriptionTerm
from app.services.subscriptions import fail


def money(value):
    return f"{Decimal(value or 0):.2f}"


def active_service(today=None):
    today = today or get_business_today()
    term = exists().where(SubscriptionTerm.subscription_id == Subscription.id,
                          SubscriptionTerm.start_date <= today, SubscriptionTerm.expiry_date > today)
    pause = exists().where(SubscriptionPause.term_id == SubscriptionTerm.id,
        SubscriptionTerm.subscription_id == Subscription.id, SubscriptionPause.start_date <= today,
        (SubscriptionPause.resumed_date.is_(None) | (SubscriptionPause.resumed_date > today)))
    due_stop = exists().where(SubscriptionEvent.subscription_id == Subscription.id,
        SubscriptionEvent.applied_at.is_(None), SubscriptionEvent.effective_date <= today,
        SubscriptionEvent.action.in_(["PAUSE", "EARLY_CLOSE"]))
    return and_(Subscription.state == "ACTIVE", term, ~pause, ~due_stop)


def scope(actor, customer_id=None, plan_id=None):
    conditions = []
    if actor.role == "CUSTOMER":
        conditions.append(Customer.user_id == actor.id)
    if customer_id:
        conditions.append(Subscription.customer_id == customer_id)
    if plan_id:
        conditions.append(Subscription.plan_id == plan_id)
    return conditions


def subscription_rows(actor, customer_id=None, plan_id=None):
    return select(Subscription.id.label("id"), Subscription.number, Subscription.customer_id,
                  Customer.name.label("customer_name"), Plan.name.label("plan_name"),
                  Subscription.state, Subscription.next_billing_date).join(Customer).join(Plan)


def receipts_query(actor, first, last, customer_id=None, plan_id=None):
    return select(Payment.id, Payment.invoice_id, Invoice.number.label("invoice_number"),
        Invoice.customer_name, Payment.amount, Payment.method, Payment.payment_date, Payment.reference).join(
        Invoice, Payment.invoice_id == Invoice.id).join(Subscription, Invoice.subscription_id == Subscription.id).join(
        Customer, Subscription.customer_id == Customer.id).where(*scope(actor, customer_id, plan_id),
        Payment.payment_date >= first, Payment.payment_date <= last)


def balances_query(actor, customer_id=None, plan_id=None, invoice_ids=None):
    payment_query = select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
    conditions = scope(actor, customer_id, plan_id)
    if conditions:
        payment_query = payment_query.join(Invoice, Payment.invoice_id == Invoice.id).join(
            Subscription, Invoice.subscription_id == Subscription.id).join(Customer, Subscription.customer_id == Customer.id).where(*conditions)
    if invoice_ids is not None:
        payment_query = payment_query.where(Payment.invoice_id.in_(invoice_ids))
    payments = payment_query.group_by(Payment.invoice_id).subquery()
    paid = func.coalesce(payments.c.paid, 0)
    remaining = case((and_(Invoice.issued_at.is_not(None), Invoice.state != "CANCELLED"),
                      func.greatest(Invoice.total - paid, 0)), else_=0)
    query = select(Invoice.id, Invoice.number, Invoice.subscription_id, Invoice.customer_id, Invoice.customer_name,
        Invoice.state, Invoice.invoice_date, Invoice.due_date, Invoice.total, Invoice.issued_at,
        paid.label("paid"), remaining.label("remaining")).join(Subscription, Invoice.subscription_id == Subscription.id).join(
        Customer, Subscription.customer_id == Customer.id).outerjoin(payments, payments.c.invoice_id == Invoice.id).where(
        *conditions)
    return query.where(Invoice.id.in_(invoice_ids)) if invoice_ids is not None else query


def normalized_range(first, last, today=None):
    today = today or get_business_today()
    first, last = first or today.replace(day=1), last or today
    if first > last:
        fail("The payment date range must end on or after its start.", 422)
    return first, last


def summary(db, actor, first=None, last=None, customer_id=None, plan_id=None, as_of=None):
    started = perf_counter()
    today = as_of or get_business_today()
    first, last = normalized_range(first, last, today)
    receipts = receipts_query(actor, first, last, customer_id, plan_id).subquery()
    balances = balances_query(actor, customer_id, plan_id).subquery()
    active = select(func.count()).select_from(Subscription).join(Customer).where(
        *scope(actor, customer_id, plan_id), active_service(today)).scalar_subquery()
    # One statement snapshot; aggregate each source once instead of repeating
    # the payment GROUP BY independently for every displayed metric.
    receipt_totals = select(func.coalesce(func.sum(receipts.c.amount), 0).label("received"),
        func.count().label("receipt_count")).subquery()
    owed = balances.c.remaining > 0
    late = and_(owed, balances.c.due_date < today)
    balance_totals = select(
        func.coalesce(func.sum(balances.c.remaining).filter(owed), 0).label("outstanding"),
        func.count().filter(owed).label("outstanding_count"),
        func.coalesce(func.sum(balances.c.remaining).filter(late), 0).label("overdue"),
        func.count().filter(late).label("overdue_count")).subquery()
    stmt = select(active.label("active_subscriptions"), *receipt_totals.c, *balance_totals.c).select_from(
        receipt_totals.join(balance_totals, true()))
    row = db.execute(stmt).mappings().one()
    return {**{key: money(value) if key in ("received", "outstanding", "overdue") else value for key, value in row.items()},
            "date_from": first, "date_to": last, "as_of_date": today, "currency": "INR",
            "query_time_ms": round((perf_counter() - started) * 1000, 2)}


def report_details(db, actor, view, first=None, last=None, customer_id=None, plan_id=None, page=1, page_size=20, sort="date", descending=None):
    started = perf_counter()
    today = get_business_today()
    first, last = normalized_range(first, last, today)
    if view == "receipts":
        query = receipts_query(actor, first, last, customer_id, plan_id)
        columns, identity = {"date": Payment.payment_date, "amount": Payment.amount, "number": Invoice.number, "customer": Invoice.customer_name}, Payment.id
    elif view in ("outstanding", "overdue"):
        rows = balances_query(actor, customer_id, plan_id).subquery()
        query = select(rows).where(rows.c.remaining > 0)
        if view == "overdue":
            query = query.where(rows.c.due_date < today)
        columns, identity = {"date": rows.c.due_date, "amount": rows.c.remaining, "number": rows.c.number, "customer": rows.c.customer_name}, rows.c.id
    else:
        query = subscription_rows(actor).where(*scope(actor, customer_id, plan_id), active_service(today))
        columns, identity = {"date": Subscription.created_at, "number": Subscription.number, "customer": Customer.name}, Subscription.id
    order = ordering(sort, descending if descending is not None else view in ("receipts", "active"), columns, identity)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(*order).offset((page - 1) * page_size).limit(page_size)).mappings()
    items = [{key: money(value) if isinstance(value, Decimal) else value for key, value in row.items()} for row in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "view": view,
            "date_from": first, "date_to": last, "as_of_date": today,
            "query_time_ms": round((perf_counter() - started) * 1000, 2)}


def dashboard(db, actor, first=None, last=None):
    started, today = perf_counter(), get_business_today()
    first, last = normalized_range(first, last, today)
    conditions = scope(actor)
    base = subscription_rows(actor).where(*conditions)
    requests = select(SubscriptionRequest.id, SubscriptionRequest.subscription_id, SubscriptionRequest.type,
        SubscriptionRequest.requested_date, Subscription.number).join(Subscription).join(Customer).where(
            *conditions, SubscriptionRequest.status == "PENDING")
    balances = balances_query(actor).subquery()
    next_date = db.scalar(select(func.min(Subscription.next_billing_date)).join(Customer).where(*conditions,
        Subscription.state.in_(["ACTIVE", "CONFIRMED"])))
    pending_stop = exists().where(SubscriptionEvent.subscription_id == Subscription.id,
        SubscriptionEvent.applied_at.is_(None), SubscriptionEvent.effective_date <= today,
        SubscriptionEvent.action.in_(["PAUSE", "EARLY_CLOSE"]))
    ending = select(Subscription.id, Subscription.number, Plan.name.label("plan_name"), SubscriptionTerm.expiry_date).join(
        SubscriptionTerm, SubscriptionTerm.subscription_id == Subscription.id).join(Customer).join(Plan).where(
        *conditions, Subscription.state.in_(["ACTIVE", "CONFIRMED"]), SubscriptionTerm.expiry_date >= today,
        SubscriptionTerm.expiry_date <= today + timedelta(days=30), ~pending_stop)
    recent_ids = select(Invoice.id).join(Subscription, Invoice.subscription_id == Subscription.id).join(
        Customer, Subscription.customer_id == Customer.id).where(*conditions, Invoice.issued_at.is_not(None)).order_by(
        Invoice.invoice_date.desc(), Invoice.id).limit(5)
    recent_balances = balances_query(actor, invoice_ids=recent_ids).subquery()
    recent_invoices = db.execute(select(recent_balances)
        .order_by(recent_balances.c.invoice_date.desc(), recent_balances.c.id)).mappings().all()
    recent_payments = db.execute(receipts_query(actor, first, last).order_by(Payment.payment_date.desc(), Payment.id).limit(5)).mappings().all()
    result = {"role": actor.role, "as_of_date": today, "date_from": first, "date_to": last, "next_billing_date": next_date,
        "pending_request_count": db.scalar(select(func.count()).select_from(requests.subquery())),
        "pending_requests": list(db.execute(requests.order_by(SubscriptionRequest.created_at, SubscriptionRequest.id).limit(5)).mappings()),
        "ending_subscriptions": list(db.execute(ending.order_by(SubscriptionTerm.expiry_date, Subscription.id).limit(5)).mappings()),
        "recent_invoices": recent_invoices, "recent_payments": recent_payments}
    if actor.role == "STAFF":
        quotes = base.where(Subscription.state == "QUOTATION")
        due = base.where(Subscription.next_billing_date <= today)
        action_invoices = balances_query(actor).where(Invoice.state == "DRAFT")
        result.update({"quote_count": db.scalar(select(func.count()).select_from(quotes.subquery())),
            "due_subscription_count": db.scalar(select(func.count()).select_from(due.subquery())),
            "invoice_action_count": db.scalar(select(func.count()).select_from(action_invoices.subquery())),
            "overdue_count": db.scalar(select(func.count()).select_from(balances).where(balances.c.remaining > 0, balances.c.due_date < today)),
            "quotes": list(db.execute(quotes.order_by(Subscription.created_at, Subscription.id).limit(5)).mappings()),
            "due_subscriptions": list(db.execute(due.order_by(Subscription.next_billing_date, Subscription.id).limit(5)).mappings())})
    else:
        metrics = summary(db, actor, first, last, as_of=today)
        if actor.role == "CUSTOMER":
            metrics = {key: metrics[key] for key in ("active_subscriptions", "outstanding", "outstanding_count", "overdue", "overdue_count")}
        result["metrics"] = metrics
    # Explicit dictionaries contain no ORM entities or internal payment actor/key.
    def serialize(value):
        if isinstance(value, Decimal):
            return money(value)
        if isinstance(value, dict):
            return {key: serialize(item) for key, item in value.items()}
        if hasattr(value, "keys"):
            return {key: serialize(item) for key, item in dict(value).items()}
        if isinstance(value, list):
            return [serialize(item) for item in value]
        return value
    result["query_time_ms"] = round((perf_counter() - started) * 1000, 2)
    return serialize(result)
