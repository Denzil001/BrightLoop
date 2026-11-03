"""Repeatable synthetic load fixture in a dedicated PostgreSQL schema.

No public/application records are deleted or changed. Financial rows are bulk
fixtures for measurement; the actual billing/payment services remain separate.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.datetime_utils import get_business_today
from app.core.security import hash_password
from app.models import (AgreementLine, AgreementLineTax, AgreementVersion, AuditEvent, Customer,
    DiscountRevision, DiscountRule, Invoice, InvoiceLine, InvoiceLineTax, Payment, Plan, PlanTax,
    Product, ProductTax, ProductVariant, QuotationTemplate, Subscription, SubscriptionEvent,
    SubscriptionPause, SubscriptionTerm, TaxRule, TemplateLine, User)
from app.services.calendar import boundary
from app.services.payments import request_hash

SCHEMA = "brightloop_benchmark"
NAMESPACE = uuid.UUID("89108ca0-52db-4d1b-a644-b2a0719ae138")
POLICIES = {key: True for key in ("allow_pause", "allow_resume", "allow_renewal", "allow_early_closure", "auto_close_on_expiry")}


def ident(value):
    return uuid.uuid5(NAMESPACE, value)


def bulk(db, model, rows):
    for offset in range(0, len(rows), 1000):
        db.execute(model.__table__.insert(), rows[offset:offset + 1000])


def seed(db, today):
    password = hash_password("Benchmark@Secure123")  # Synthetic benchmark identities only.
    bulk(db, User, [{"id": ident(role), "name": f"Benchmark {role.title()}",
        "email_normalized": f"benchmark_{role}@brightloop.test", "role": role.upper(),
        "password_hash": password, "active": True} for role in ("admin", "staff", "customer")])
    bulk(db, Customer, [{"id": ident(f"customer-{i}"), "name": f"Benchmark customer {i:04d}",
        "email_normalized": f"benchmark_client_{i:04d}@brightloop.test", "company": f"Synthetic company {i:04d}",
        "user_id": ident("customer") if i == 0 else None} for i in range(500)])
    bulk(db, TaxRule, [{"id": ident("tax"), "name": "Benchmark GST", "classification": "GST", "rate": Decimal("18.00")}])
    intervals = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
    bulk(db, Plan, [{"id": ident(f"plan-{i}"), "name": f"Benchmark {interval.title()}", "interval": interval,
        "base_fee": Decimal("1000.00"), "minimum_seats": 1, "extra_seat_unit_price": Decimal("50.00"), **POLICIES}
        for i, interval in enumerate(intervals)])
    bulk(db, PlanTax, [{"plan_id": ident(f"plan-{i}"), "tax_rule_id": ident("tax")} for i in range(4)])
    bulk(db, Product, [{"id": ident(f"product-{i}"), "name": f"Benchmark product {i:04d}", "type": "SOFTWARE",
        "sales_price": Decimal("200.00"), "cost_price": Decimal("80.00"), "notes": "Synthetic benchmark catalog"} for i in range(200)])
    bulk(db, ProductTax, [{"product_id": ident(f"product-{i}"), "tax_rule_id": ident("tax")} for i in range(200)])
    bulk(db, ProductVariant, [{"id": ident(f"variant-{i}"), "product_id": ident(f"product-{i}"),
        "name": "Odoo", "price_adjustment": Decimal("560.00")} for i in range(200)])
    bulk(db, QuotationTemplate, [{"id": ident(f"template-{i}"), "name": f"Benchmark template {i:04d}",
        "plan_id": ident("plan-0"), "validity_days": 30, "active": True} for i in range(200)])
    bulk(db, TemplateLine, [{"id": ident(f"template-line-{i}"), "template_id": ident(f"template-{i}"), "ordinal": 1,
        "product_id": ident(f"product-{i}"), "quantity": 1, "line_kind": "ADDON"} for i in range(200)])
    bulk(db, DiscountRule, [{"id": ident(f"discount-{i}"), "name": f"Benchmark discount {i:04d}"} for i in range(200)])
    bulk(db, DiscountRevision, [{"id": ident(f"revision-{i}"), "rule_id": ident(f"discount-{i}"), "revision": 1,
        "type": "PERCENT", "scope": "SUBSCRIPTION", "rate": Decimal("10.00"),
        "valid_from": today - timedelta(days=30), "valid_to": today + timedelta(days=365)} for i in range(200)])
    rows = {model: [] for model in (Subscription, SubscriptionTerm, AgreementVersion, AgreementLine,
        AgreementLineTax, SubscriptionEvent, SubscriptionPause, Invoice, InvoiceLine, InvoiceLineTax, Payment, AuditEvent)}
    issuer = get_settings().issuer_address_dict
    estimate = {"subtotal": "1000.00", "total_discount": "0.00", "total_tax": "180.00", "total": "1180.00",
        "lines": [{"ordinal": 1, "description": "Plan fee", "quantity": 1, "unit_price": "1000.00",
            "subtotal": "1000.00", "discount_amount": "0.00", "tax_amount": "180.00", "total": "1180.00"}]}
    for i in range(5000):
        sub_id, term_id, agreement_id = (ident(f"{kind}-{i}") for kind in ("subscription", "term", "agreement"))
        interval = intervals[i % 4]
        if interval == "DAILY":
            start = today - timedelta(days=10)
        elif interval == "WEEKLY":
            start = today - timedelta(days=70)
        elif interval == "MONTHLY":
            year, month = divmod(today.year * 12 + today.month - 1 - 10, 12)
            start = date(year, month + 1, 1)
        else:
            start = date(today.year - 10, 1, 1)
        cursor = boundary(start, interval, 10)
        state = "ACTIVE" if i % 20 < 14 else "CLOSED" if i % 20 < 17 else "PAUSED"
        expiry = cursor if state == "CLOSED" else boundary(start, interval, 12)
        customer_id = ident(f"customer-{i % 500}")
        issued = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        rows[Subscription].append({"id": sub_id, "number": f"BENCH-SUB-{i:05d}", "customer_id": customer_id,
            "plan_id": ident(f"plan-{i % 4}"), "creator_id": ident("admin"), "state": state, "seat_quantity": 1,
            "next_billing_date": cursor if state == "ACTIVE" else None})
        rows[AgreementVersion].append({"id": agreement_id, "subscription_id": sub_id, "sequence": 1,
            "state": "ACCEPTED", "quote_number": f"BENCH-QUO-{i:05d}", "issued_date": start,
            "valid_until": start + timedelta(days=30), "accepted_at": issued, "effective_from": start,
            "seat_quantity": 1, "proposed_start_date": start, "proposed_expiry_date": expiry,
            "proposed_interval": interval, "payment_term_days": 15, "currency": "INR",
            "policy_snapshot": POLICIES, "pricing_snapshot": estimate})
        rows[SubscriptionTerm].append({"id": term_id, "subscription_id": sub_id, "sequence": 1, "start_date": start,
            "expiry_date": expiry, "original_anchor_date": start, "interval": interval,
            "source_version_id": agreement_id, **POLICIES})
        line_id = ident(f"agreement-line-{i}")
        rows[AgreementLine].append({"id": line_id, "version_id": agreement_id, "ordinal": 1, "kind": "PLAN_FEE",
            "snapshot_name": f"Benchmark {interval.title()} plan fee", "quantity": 1, "unit_price": Decimal("1000.00")})
        rows[AgreementLineTax].append({"line_id": line_id, "source_tax_id": ident("tax"), "snapshot_name": "Benchmark GST",
            "snapshot_classification": "GST", "snapshot_rate": Decimal("18.00")})
        if state in ("CLOSED", "PAUSED"):
            event_id = ident(f"event-{i}")
            rows[SubscriptionEvent].append({"id": event_id, "subscription_id": sub_id, "term_id": term_id,
                "action": "AUTO_CLOSE" if state == "CLOSED" else "PAUSE", "effective_date": cursor,
                "applied_at": datetime.combine(cursor, datetime.min.time(), tzinfo=timezone.utc), "payload": {"source": "BENCHMARK_FIXTURE"}})
            if state == "PAUSED":
                rows[SubscriptionPause].append({"term_id": term_id, "start_date": cursor,
                    "original_expiry_date": expiry, "pause_event_id": event_id})
        for period in range(10):
            invoice_id = ident(f"invoice-{i}-{period}")
            invoice_line_id = ident(f"invoice-line-{i}-{period}")
            first, last = boundary(start, interval, period), boundary(start, interval, period + 1)
            category = (i * 10 + period) % 4
            amounts = ("400.00", "400.00", "380.00") if category < 2 else ("200.00", "200.00") if category == 2 else ()
            rows[Invoice].append({"id": invoice_id, "number": f"BENCH-INV-{i:05d}-{period:02d}",
                "subscription_id": sub_id, "term_id": term_id, "agreement_id": agreement_id, "customer_id": customer_id,
                "period_start": first, "period_end": last, "full_period_end": last,
                "service_days": (last - first).days, "full_period_days": (last - first).days,
                "invoice_date": first, "due_date": first + timedelta(days=15), "currency": "INR",
                "state": "PAID" if category < 2 else "PARTIALLY_PAID" if category == 2 else "CONFIRMED",
                "subtotal": Decimal("1000.00"), "discount_total": Decimal("0.00"), "tax_total": Decimal("180.00"),
                "total": Decimal("1180.00"), "issuer_name": issuer["name"], "issuer_address": issuer,
                "customer_name": f"Benchmark customer {i % 500:04d}",
                "customer_email": f"benchmark_client_{i % 500:04d}@brightloop.test", "customer_address": {},
                "issued_at": datetime.combine(first, datetime.min.time(), tzinfo=timezone.utc)})
            rows[InvoiceLine].append({"id": invoice_line_id, "invoice_id": invoice_id, "ordinal": 1,
                "agreement_line_id": line_id, "snapshot_description": f"Benchmark {interval.title()} plan fee",
                "quantity": 1, "unit_price": Decimal("1000.00"), "subtotal": Decimal("1000.00"),
                "discount_amount": Decimal("0.00"), "tax_amount": Decimal("180.00"), "total": Decimal("1180.00")})
            rows[InvoiceLineTax].append({"invoice_line_id": invoice_line_id, "source_tax_id": ident("tax"),
                "snapshot_name": "Benchmark GST", "snapshot_rate": Decimal("18.00"),
                "taxable_base": Decimal("1000.00"), "amount": Decimal("180.00")})
            for payment_index, amount in enumerate(amounts):
                payload = SimpleNamespace(amount=Decimal(amount), method=("BANK_TRANSFER", "UPI", "CASH")[payment_index],
                    payment_date=first, note="Synthetic benchmark payment", reference=f"BENCH-{i}-{period}-{payment_index}")
                rows[Payment].append({"id": ident(f"payment-{i}-{period}-{payment_index}"), "invoice_id": invoice_id,
                    "amount": payload.amount, "method": payload.method, "payment_date": first, "note": payload.note,
                    "reference": payload.reference, "recorded_by": ident("staff"),
                    "request_key": f"benchmark-{i}-{period}-{payment_index}", "request_hash": request_hash(invoice_id, payload)})
            rows[AuditEvent].append({"actor_id": ident("admin"), "action": "BENCHMARK_INVOICE_SEEDED",
                "target_type": "invoice", "target_id": str(invoice_id), "payload": {"synthetic": True}})
    for model in (Subscription, AgreementVersion, SubscriptionTerm, AgreementLine, AgreementLineTax,
                  SubscriptionEvent, SubscriptionPause, Invoice, InvoiceLine, InvoiceLineTax, Payment, AuditEvent):
        bulk(db, model, rows[model])
        print(f"Seeded {model.__tablename__}: {len(rows[model])}", flush=True)
    # Complete the circular link after both sides exist, without changing history.
    db.execute(text("UPDATE agreement_versions v SET term_id=t.id FROM subscription_terms t WHERE t.source_version_id=v.id"))
    db.add(AuditEvent(id=ident("seed-marker"), action="BENCHMARK_SEEDED", target_type="benchmark", target_id="v1",
        payload={"as_of_date": today.isoformat(), "synthetic": True}))


def main():
    settings = get_settings()
    source_url = make_url(settings.DATABASE_URL)
    if source_url.get_backend_name() != "postgresql" or source_url.query.get("options"):
        raise RuntimeError("Seed creation requires the normal local PostgreSQL URL without custom search_path options.")
    source = create_engine(source_url)
    with source.begin() as connection:
        before = connection.scalar(text("SELECT count(*) FROM public.subscriptions"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS brightloop_benchmark"))
    url = source_url.update_query_dict({"options": f"-csearch_path={SCHEMA}"})
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_engine(url, isolation_level="READ COMMITTED")
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_schema()")) == SCHEMA
        marker = db.get(AuditEvent, ident("seed-marker"))
        if not marker:
            if db.scalar(select(func.count()).select_from(Subscription)):
                raise RuntimeError("Benchmark schema is not empty and has no completed seed marker; inspect it before proceeding.")
            seed(db, get_business_today())
            db.commit()
            marker = db.get(AuditEvent, ident("seed-marker"))
        counts = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in (Subscription, Invoice, Payment, Customer)}
        assert counts["subscriptions"] >= 5000 and counts["invoices"] >= 50000 and counts["payments"] >= 100000
        mismatch = db.scalar(text("""SELECT count(*) FROM invoices i LEFT JOIN
            (SELECT invoice_id, sum(amount) paid FROM payments GROUP BY invoice_id) p ON p.invoice_id=i.id
            WHERE coalesce(p.paid,0)>i.total OR (i.state='PAID') <> (coalesce(p.paid,0)=i.total)"""))
        assert mismatch == 0
        assert db.scalar(text("SELECT count(*) FROM payments WHERE payment_date>CURRENT_DATE")) == 0
    with engine.begin() as connection:
        connection.execute(text("ANALYZE"))
    with source.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM public.subscriptions")) == before
    # Private config is ignored; no URL or credential is emitted.
    (ROOT / "backend/.env.benchmark").write_text(f"DATABASE_URL={url.render_as_string(hide_password=False)}\nFRONTEND_ORIGIN=http://localhost:3001\nAPP_ENV=benchmark\n", encoding="utf-8")
    manifest = {"schema": SCHEMA, "seed_date": marker.payload["as_of_date"], "counts": counts,
        "public_subscription_count_unchanged": before,
        "customer_id": str(ident("customer-0")), "subscription_id": str(ident("subscription-0")),
        "invoice_id": str(ident("invoice-0-0")), "payment_id": str(ident("payment-0-0-0")),
        "product_id": str(ident("product-0")), "plan_id": str(ident("plan-0")), "template_id": str(ident("template-0"))}
    (ROOT / "test-results").mkdir(exist_ok=True)
    (ROOT / "test-results/benchmark-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
