"""Accepted D06: disjoint product rules coexist; overlapping scopes do not."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.datetime_utils import get_business_today
from app.models.catalog import Product
from app.models.discounts import DiscountProduct, DiscountRedemption, DiscountRevision, DiscountRule
from app.models.taxes import ProductTax, TaxRule
from app.schemas.pricing import PricingLineInput, PricingPreviewRequest
from app.services.pricing import PricingError, PricingService
from test_subscriptions import create, draft_data


@pytest.fixture
def discount_case(db, draft_data):
    today = get_business_today()
    products = [Product(name="Product A", type="ADDON", sales_price=Decimal("100.00"), cost_price=Decimal("20.00")),
                Product(name="Product B", type="ADDON", sales_price=Decimal("200.00"), cost_price=Decimal("30.00"))]
    db.add_all(products)
    db.flush()
    tax = db.scalar(select(TaxRule).where(TaxRule.name == "GST"))
    for product in products:
        db.add(ProductTax(product_id=product.id, tax_rule_id=tax.id))
    rules, revisions = [], []
    for i, scope in enumerate(["PRODUCT", "PRODUCT", "PRODUCT", "SUBSCRIPTION"]):
        rule = DiscountRule(name=f"D06 rule {i}")
        db.add(rule)
        db.flush()
        revision = DiscountRevision(rule_id=rule.id, revision=1, scope=scope,
            type="FIXED" if i == 1 else "PERCENT", amount=Decimal("30.00") if i == 1 else None,
            rate=None if i == 1 else Decimal("10.00"), valid_from=today, valid_to=today + timedelta(days=365))
        db.add(revision)
        db.flush()
        if scope == "PRODUCT":
            db.add(DiscountProduct(revision_id=revision.id, product_id=products[1 if i == 1 else 0].id))
        rules.append(rule)
        revisions.append(revision)
    db.commit()
    request = PricingPreviewRequest(plan_id=draft_data["plan_id"], seat_quantity=5,
                                    lines=[PricingLineInput(product_id=p.id, quantity=1) for p in products],
                                    discount_ids=[rules[0].id, rules[1].id])
    return request, rules, revisions


def test_disjoint_rules_tax_reconciliation_and_no_preview_redemption(db, discount_case):
    request, rules, revisions = discount_case
    for _ in range(2):
        result = PricingService.calculate_pricing(db, request)
        assert result.subtotal == "1300.00"
        assert result.total_discount == "40.00"
        assert result.total_tax == "226.80"
        assert result.total == "1486.80"
        assert result.assigned_discount_revision_ids == [revisions[0].id, revisions[1].id]
        assert len(result.applied_discount_revision_ids) == 2
        assert sum(Decimal(t.taxable_base) for t in result.tax_breakdown) == Decimal("1260.00")
    assert db.scalar(select(func.count()).select_from(DiscountRedemption)) == 0


@pytest.mark.parametrize("indices", [[0, 0], [0, 2], [0, 3]])
def test_duplicate_overlapping_and_whole_rules_rejected(db, discount_case, indices):
    request, rules, _ = discount_case
    request.discount_ids = [rules[index].id for index in indices]
    with pytest.raises(PricingError):
        PricingService.calculate_pricing(db, request)


def test_quote_pins_both_exact_revisions(client, db, admin_auth, draft_data, discount_case):
    request, rules, revisions = discount_case
    sub = create(client, admin_auth, {**draft_data, "seat_quantity": 5,
        "lines": [line.model_dump(mode="json") for line in request.lines],
        "discount_ids": [str(rules[0].id), str(rules[1].id)]})
    quote = sub["agreements"][0]
    assert set(quote["discount_revision_ids"]) == {str(revisions[0].id), str(revisions[1].id)}
    assert quote["pricing_estimate"]["total"] == "1486.80"
