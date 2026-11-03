"""Independent PostgreSQL connections verify billing and global cap races."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import String, cast, delete, func, select, text, update
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.billing import BillingOutcome, EmailAttempt
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.discounts import DiscountRedemption, DiscountRevision, DiscountRule
from app.models.invoices import Invoice, InvoiceLine, InvoiceLineDiscount, InvoiceLineTax
from app.models.subscriptions import (AgreementDiscount, AgreementLine, AgreementLineTax, AgreementVersion,
    Subscription, SubscriptionEvent, SubscriptionPause, SubscriptionTerm)
from app.models.users import CommandReceipt, User
from app.models.payments import Payment
from app.schemas.subscriptions import SubscriptionCommand, SubscriptionDraft
from app.services.billing import process_next_period
from app.services.subscriptions import create_draft, execute_command


@contextmanager
def committed_case(count):
    ids = {}
    suffix = uuid.uuid4().hex
    try:
        with Session(test_engine) as db:
            actor = User(email_normalized=f"billing_actor_{suffix}@brightloop.test", name="Billing race actor",
                         password_hash=hash_password("Billing@Race123"), role="ADMIN", active=True)
            customer = Customer(name="Billing race", email_normalized=f"billing_customer_{suffix}@brightloop.test")
            plan = Plan(name=f"Billing race {suffix}", base_fee=Decimal("1000.00"), minimum_seats=1,
                        extra_seat_unit_price=Decimal("0.00"), interval="MONTHLY")
            rule = DiscountRule(name=f"Billing race cap {suffix}", maximum_uses=1)
            db.add_all([actor, customer, plan, rule])
            db.flush()
            ids.update(actor=actor.id, customer=customer.id, plan=plan.id, rule=rule.id, subscriptions=[])
            db.add(DiscountRevision(rule_id=rule.id, revision=1, type="PERCENT", scope="SUBSCRIPTION",
                rate=Decimal("10.00"), valid_from=date(2025, 1, 1), valid_to=date(2027, 1, 1)))
            db.flush()
            for _ in range(count):
                sub = create_draft(db, SubscriptionDraft(customer_id=customer.id, plan_id=plan.id,
                    seat_quantity=1, start_date=date(2025, 1, 31), expiry_date=date(2025, 4, 30), discount_id=rule.id), actor)
                for action in ("ISSUE", "CONFIRM", "ACTIVATE"):
                    execute_command(db, sub, SubscriptionCommand(action=action, expected_version=sub.version,
                                                                 request_key=uuid.uuid4().hex), actor)
                ids["subscriptions"].append(sub.id)
            db.commit()
        yield ids
    finally:
        if ids:
            with Session(test_engine) as db:
                subs = ids["subscriptions"]
                invoice_ids = select(Invoice.id).where(Invoice.subscription_id.in_(subs))
                line_ids = select(InvoiceLine.id).where(InvoiceLine.invoice_id.in_(invoice_ids))
                versions = select(AgreementVersion.id).where(AgreementVersion.subscription_id.in_(subs))
                agreement_lines = select(AgreementLine.id).where(AgreementLine.version_id.in_(versions))
                db.execute(delete(AuditEvent).where(AuditEvent.target_type == "invoice", AuditEvent.target_id.in_(
                    select(cast(Invoice.id, String)).where(Invoice.subscription_id.in_(subs)))))
                if db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id.in_(invoice_ids))):
                    # Committed race tests use the isolated owner-only test DB.
                    # Bypass immutability only for teardown, transactionally; the
                    # trigger remains enabled throughout application/race tests.
                    db.execute(text("ALTER TABLE payments DISABLE TRIGGER payments_immutable"))
                    db.execute(delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
                    db.execute(text("ALTER TABLE payments ENABLE TRIGGER payments_immutable"))
                db.execute(delete(InvoiceLineDiscount).where(InvoiceLineDiscount.invoice_id.in_(invoice_ids)))
                db.execute(delete(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id.in_(line_ids)))
                db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids)))
                db.execute(delete(DiscountRedemption).where(DiscountRedemption.invoice_id.in_(invoice_ids)))
                db.execute(delete(BillingOutcome).where(BillingOutcome.subscription_id.in_(subs)))
                db.execute(delete(EmailAttempt).where(EmailAttempt.invoice_id.in_(invoice_ids)))
                db.execute(delete(Invoice).where(Invoice.subscription_id.in_(subs)))
                db.execute(delete(SubscriptionPause).where(SubscriptionPause.term_id.in_(select(SubscriptionTerm.id).where(SubscriptionTerm.subscription_id.in_(subs)))))
                db.execute(delete(SubscriptionEvent).where(SubscriptionEvent.subscription_id.in_(subs)))
                db.execute(update(SubscriptionTerm).where(SubscriptionTerm.subscription_id.in_(subs)).values(source_version_id=None))
                db.execute(update(AgreementVersion).where(AgreementVersion.subscription_id.in_(subs)).values(term_id=None))
                db.execute(delete(SubscriptionTerm).where(SubscriptionTerm.subscription_id.in_(subs)))
                db.execute(delete(AgreementLineTax).where(AgreementLineTax.line_id.in_(agreement_lines)))
                db.execute(delete(AgreementDiscount).where(AgreementDiscount.version_id.in_(versions)))
                db.execute(delete(AgreementLine).where(AgreementLine.version_id.in_(versions)))
                db.execute(delete(AgreementVersion).where(AgreementVersion.subscription_id.in_(subs)))
                db.execute(delete(Subscription).where(Subscription.id.in_(subs)))
                db.execute(delete(CommandReceipt).where(CommandReceipt.actor_id == ids["actor"]))
                db.execute(delete(DiscountRevision).where(DiscountRevision.rule_id == ids["rule"]))
                db.execute(delete(DiscountRule).where(DiscountRule.id == ids["rule"]))
                db.execute(delete(Customer).where(Customer.id == ids["customer"]))
                db.execute(delete(Plan).where(Plan.id == ids["plan"]))
                db.execute(delete(AuditEvent).where(AuditEvent.actor_id == ids["actor"]))
                db.execute(delete(User).where(User.id == ids["actor"]))
                db.commit()


def process(subscription_id):
    with Session(test_engine) as db:
        result = process_next_period(db, subscription_id, date(2025, 1, 31))
        db.commit()
        return result


def test_same_period_concurrent_calls_one_invoice_and_one_advance():
    with committed_case(1) as ids:
        subscription_id = ids["subscriptions"][0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(process, [subscription_id, subscription_id]))
        assert sorted(result.state for result in results) == ["CREATED", "EXISTING"]
        assert results[0].invoice_id == results[1].invoice_id
        with Session(test_engine) as db:
            assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.subscription_id == subscription_id)) == 1
            subscription = db.get(Subscription, subscription_id)
            assert subscription.version == 5
            assert subscription.next_billing_date == date(2025, 2, 28)


def test_different_subscriptions_compete_for_one_global_discount_use():
    with committed_case(2) as ids:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(process, ids["subscriptions"]))
        assert all(result.state == "CREATED" for result in results)
        with Session(test_engine) as db:
            invoices = db.scalars(select(Invoice).where(Invoice.subscription_id.in_(ids["subscriptions"]))).all()
            assert sorted(invoice.total for invoice in invoices) == [Decimal("900.00"), Decimal("1000.00")]
            assert db.scalar(select(func.count()).select_from(DiscountRedemption).where(DiscountRedemption.rule_id == ids["rule"])) == 1
