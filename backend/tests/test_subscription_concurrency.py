"""Real independent PostgreSQL transactions serialize duplicate confirmation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.datetime_utils import get_business_today
from app.core.security import hash_password
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.subscriptions import (AgreementLine, AgreementVersion, Subscription,
                                      SubscriptionEvent, SubscriptionTerm)
from app.models.users import CommandReceipt, User
from app.schemas.subscriptions import SubscriptionCommand, SubscriptionDraft
from app.services.subscriptions import create_draft, execute_command, load_subscription


def test_concurrent_confirmation_one_term_and_receipt():
    # Unlike the savepoint-backed API fixtures, these synthetic rows are committed
    # so both independent connections can observe them. Cleanup is test-DB-only.
    suffix = uuid.uuid4().hex
    ids = {}
    try:
        with Session(test_engine) as db:
            actor = User(email_normalized=f"confirm_{suffix}@brightloop.test", name="Concurrency actor",
                         password_hash=hash_password("Concurrency@123"), role="ADMIN", active=True)
            customer = Customer(email_normalized=f"confirm_customer_{suffix}@brightloop.test", name="Concurrency customer")
            plan = Plan(name=f"Concurrency plan {suffix}", base_fee=Decimal("10.00"), minimum_seats=1,
                        extra_seat_unit_price=Decimal("0.00"), interval="DAILY")
            db.add_all([actor, customer, plan])
            db.flush()
            ids.update(actor=actor.id, customer=customer.id, plan=plan.id)
            today = get_business_today()
            sub = create_draft(db, SubscriptionDraft(customer_id=customer.id, plan_id=plan.id, seat_quantity=1,
                               start_date=today, expiry_date=today + timedelta(days=30)), actor)
            ids["subscription"] = sub.id
            execute_command(db, sub, SubscriptionCommand(action="ISSUE", expected_version=sub.version,
                                                         request_key=uuid.uuid4().hex), actor)
            expected_version = sub.version
            db.commit()
        command = SubscriptionCommand(action="CONFIRM", expected_version=expected_version, request_key=uuid.uuid4().hex)

        def confirm():
            with Session(test_engine) as db:
                actor = db.get(User, ids["actor"])
                sub = load_subscription(db, ids["subscription"], actor, lock=True)
                execute_command(db, sub, command, actor)
                db.commit()
                return sub.version

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: confirm(), range(2)))
        assert results == [expected_version + 1, expected_version + 1]
        with Session(test_engine) as db:
            assert db.scalar(select(func.count()).select_from(SubscriptionTerm).where(SubscriptionTerm.subscription_id == ids["subscription"])) == 1
            assert db.scalar(select(func.count()).select_from(CommandReceipt).where(CommandReceipt.actor_id == ids["actor"], CommandReceipt.request_key == command.request_key)) == 1
    finally:
        with Session(test_engine) as db:
            if "subscription" in ids:
                sub_id = ids["subscription"]
                version_ids = select(AgreementVersion.id).where(AgreementVersion.subscription_id == sub_id)
                db.execute(delete(SubscriptionEvent).where(SubscriptionEvent.subscription_id == sub_id))
                db.execute(update(SubscriptionTerm).where(SubscriptionTerm.subscription_id == sub_id).values(source_version_id=None))
                db.execute(update(AgreementVersion).where(AgreementVersion.subscription_id == sub_id).values(term_id=None))
                db.execute(delete(SubscriptionTerm).where(SubscriptionTerm.subscription_id == sub_id))
                db.execute(delete(AgreementLine).where(AgreementLine.version_id.in_(version_ids)))
                db.execute(delete(AgreementVersion).where(AgreementVersion.subscription_id == sub_id))
                db.execute(delete(Subscription).where(Subscription.id == sub_id))
            if "actor" in ids:
                db.execute(delete(CommandReceipt).where(CommandReceipt.actor_id == ids["actor"]))
                db.execute(delete(User).where(User.id == ids["actor"]))
                db.execute(delete(Customer).where(Customer.id == ids["customer"]))
                db.execute(delete(Plan).where(Plan.id == ids["plan"]))
            db.commit()
