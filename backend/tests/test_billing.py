"""Historical billing uses accepted snapshots and durable period identities."""
from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import func, select

from app.models.catalog import Plan, Product, ProductVariant
from app.models.discounts import DiscountRedemption, DiscountRevision, DiscountRule
from app.models.invoices import Invoice, InvoiceLineDiscount
from app.models.subscriptions import Subscription, SubscriptionEvent, SubscriptionTerm
from app.models.taxes import ProductTax, TaxRule
from app.schemas.subscriptions import SubscriptionCommand, SubscriptionDraft
from app.services.billing import process_next_period
from app.services.subscriptions import create_draft, execute_command
from test_subscriptions import draft_data


def contract(db, actor, data, **patch):
    payload = SubscriptionDraft(**{**data, "start_date": "2025-01-31", "expiry_date": "2025-04-15", **patch})
    subscription = create_draft(db, payload, actor)
    for action in ("ISSUE", "CONFIRM", "ACTIVATE"):
        execute_command(db, subscription, SubscriptionCommand(action=action, expected_version=subscription.version,
                                                              request_key=uuid.uuid4().hex), actor)
    db.commit()
    return subscription


def test_historical_catchup_final_proration_and_replay(db, admin_auth, draft_data):
    subscription = contract(db, admin_auth["user"], draft_data)
    plan = db.get(Plan, subscription.plan_id)
    plan.base_fee = Decimal("9000.00")
    plan.active = False
    db.scalar(select(TaxRule).where(TaxRule.name == "GST")).rate = Decimal("5.00")
    subscription.state = "CLOSED"  # current state must not erase owed historical service
    subscription.next_billing_date = None
    db.commit()
    results = []
    for _ in range(3):
        results.append(process_next_period(db, subscription.id, date(2025, 4, 20)))
        db.commit()
    invoices = db.scalars(select(Invoice).order_by(Invoice.period_start)).all()
    assert [r.state for r in results] == ["CREATED"] * 3
    assert [i.period_start for i in invoices] == [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)]
    assert [i.total for i in invoices] == [Decimal("1416.00"), Decimal("1416.00"), Decimal("708.00")]
    assert invoices[-1].period_end == date(2025, 4, 15)
    assert invoices[-1].full_period_end == date(2025, 4, 30)
    assert (invoices[-1].service_days, invoices[-1].full_period_days) == (15, 30)
    assert all(i.invoice_date == date(2025, 4, 20) and i.due_date == date(2025, 5, 5) for i in invoices)
    version = subscription.version
    replay = process_next_period(db, subscription.id, date(2025, 5, 15))
    db.commit()
    assert replay.state == "EXISTING"
    assert subscription.version == version
    assert db.scalar(select(func.count()).select_from(Invoice)) == 3
    assert invoices[0].invoice_date == date(2025, 4, 20)
    assert subscription.next_billing_date is None


def test_worked_amount_discount_cap_and_atomic_rollback(db, admin_auth, draft_data):
    product = Product(name="Server", type="SERVER", sales_price=Decimal("200.00"), cost_price=Decimal("80.00"))
    rule = DiscountRule(name="Whole ten percent", maximum_uses=1)
    db.add_all([product, rule])
    db.flush()
    variant = ProductVariant(product_id=product.id, name="High memory", price_adjustment=Decimal("560.00"))
    revision = DiscountRevision(rule_id=rule.id, revision=1, type="PERCENT", scope="SUBSCRIPTION",
                                rate=Decimal("10.00"), valid_from=date(2025, 1, 1), valid_to=date(2027, 1, 1))
    db.add_all([variant, revision])
    db.add(ProductTax(product_id=product.id, tax_rule_id=db.scalar(select(TaxRule.id))))
    db.commit()
    subscription = contract(db, admin_auth["user"], draft_data, discount_id=rule.id,
                            lines=[{"product_id": product.id, "variant_id": variant.id, "quantity": 2}])
    initial_version = subscription.version
    with pytest.raises(RuntimeError, match="simulated"):
        with db.begin_nested():
            result = process_next_period(db, subscription.id, date(2025, 3, 1))
            assert db.get(Invoice, result.invoice_id).total == Decimal("2888.64")
            raise RuntimeError("simulated transient failure after financial writes")
    assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    assert db.scalar(select(func.count()).select_from(DiscountRedemption)) == 0
    assert subscription.version == initial_version
    first = process_next_period(db, subscription.id, date(2025, 3, 1))
    db.commit()
    second = process_next_period(db, subscription.id, date(2025, 3, 1))
    db.commit()
    assert db.get(Invoice, first.invoice_id).total == Decimal("2888.64")
    assert db.get(Invoice, second.invoice_id).total == Decimal("3209.60")
    assert db.scalar(select(func.count()).select_from(DiscountRedemption)) == 1
    assert db.scalar(select(func.sum(InvoiceLineDiscount.allocated_amount))) == Decimal("272.00")


def test_due_pause_and_resume_preserve_earlier_backlog(db, admin_auth, draft_data):
    subscription = contract(db, admin_auth["user"], draft_data, start_date="2025-01-01", expiry_date="2026-01-01")
    term = db.scalar(select(SubscriptionTerm))
    pause = SubscriptionEvent(subscription_id=subscription.id, term_id=term.id, action="PAUSE",
                              effective_date=date(2025, 2, 1), actor_id=admin_auth["user"].id)
    db.add(pause)
    db.commit()
    first = process_next_period(db, subscription.id, date(2025, 2, 5))
    db.commit()
    assert first.period_start == date(2025, 1, 1)
    assert pause.applied_at is None
    process_next_period(db, subscription.id, date(2025, 2, 5))
    db.commit()
    assert subscription.state == "PAUSED"
    assert subscription.next_billing_date is None
    assert db.scalar(select(func.count()).select_from(Invoice)) == 1
    db.add(SubscriptionEvent(subscription_id=subscription.id, term_id=term.id, action="RESUME",
                             effective_date=date(2025, 2, 11), actor_id=admin_auth["user"].id))
    db.commit()
    resumed = process_next_period(db, subscription.id, date(2025, 2, 12))
    db.commit()
    assert resumed.period_start == date(2025, 2, 11)
    assert term.expiry_date == date(2026, 1, 11)
    assert subscription.next_billing_date == date(2025, 3, 11)
    assert subscription.state == "ACTIVE"
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.period_start == date(2025, 2, 1))) == 0


@pytest.mark.parametrize("interval,start,expiry,expected", [
    ("DAILY", "2025-02-27", "2025-03-02", [date(2025, 2, 27), date(2025, 2, 28), date(2025, 3, 1)]),
    ("WEEKLY", "2025-01-01", "2025-01-20", [date(2025, 1, 1), date(2025, 1, 8), date(2025, 1, 15)]),
    ("YEARLY", "2024-02-29", "2028-03-01", [date(2024, 2, 29), date(2025, 2, 28), date(2026, 2, 28), date(2027, 2, 28), date(2028, 2, 29)]),
])
def test_billing_all_other_intervals_preserve_calendar_anchors(db, admin_auth, draft_data, interval, start, expiry, expected):
    plan = db.get(Plan, uuid.UUID(draft_data["plan_id"]))
    plan.interval = interval
    db.commit()
    subscription = contract(db, admin_auth["user"], draft_data, start_date=start, expiry_date=expiry)
    for _ in expected:
        result = process_next_period(db, subscription.id, date.fromisoformat(expiry))
        db.commit()
        assert result.state == "CREATED"
    invoices = db.scalars(select(Invoice).order_by(Invoice.period_start)).all()
    assert [invoice.period_start for invoice in invoices] == expected
    assert invoices[-1].period_end == date.fromisoformat(expiry)
    assert process_next_period(db, subscription.id, date.fromisoformat(expiry)).state == "EXISTING"
