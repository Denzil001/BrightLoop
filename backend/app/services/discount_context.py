"""Resolve immutable revisions and evaluate current cap/historical cutoff context."""
from sqlalchemy import func, select

from app.models.discounts import DiscountProduct, DiscountRedemption, DiscountRevision, DiscountRule
from app.services.financial_calculator import Discount, PricingError


def resolve_revisions(db, rule_ids, revision_ids, as_of):
    if len(rule_ids) + len(revision_ids) > 10:
        raise PricingError("Assign no more than ten discount rules.")
    revisions = []
    for rule_id in rule_ids:
        revision = db.scalar(select(DiscountRevision).where(DiscountRevision.rule_id == rule_id,
            DiscountRevision.valid_from <= as_of, DiscountRevision.valid_to >= as_of)
            .order_by(DiscountRevision.revision.desc()).limit(1))
        if revision is None:
            revision = db.scalar(select(DiscountRevision).where(DiscountRevision.rule_id == rule_id)
                                 .order_by(DiscountRevision.revision.desc()).limit(1))
        if revision is None:
            raise PricingError("An assigned discount rule has no available revision.")
        revisions.append(revision)
    for revision_id in revision_ids:
        revision = db.get(DiscountRevision, revision_id)
        if revision is None:
            raise PricingError("An assigned discount revision was not found.")
        revisions.append(revision)
    return revisions


def load_terms(db, revisions, as_of, lock_rules=False):
    rule_ids = sorted({revision.rule_id for revision in revisions})
    query = select(DiscountRule).where(DiscountRule.id.in_(rule_ids)).order_by(DiscountRule.id)
    if lock_rules:
        query = query.with_for_update().execution_options(populate_existing=True)
    rules = {rule.id: rule for rule in db.scalars(query)}
    # Lock acquisition precedes this count. READ COMMITTED now sees the winning
    # transaction's redemption before a competing invoice evaluates its cap.
    used = dict(db.execute(select(DiscountRedemption.rule_id, func.count()).where(
        DiscountRedemption.rule_id.in_(rule_ids)).group_by(DiscountRedemption.rule_id)).all())
    products = {}
    for revision_id, product_id in db.execute(select(DiscountProduct.revision_id, DiscountProduct.product_id)
                                            .where(DiscountProduct.revision_id.in_([revision.id for revision in revisions]))):
        products.setdefault(revision_id, set()).add(product_id)
    terms = []
    for revision in revisions:
        rule = rules.get(revision.rule_id)
        if rule is None:
            raise PricingError("An assigned discount rule was not found.")
        reason = None
        if rule.disabled_from and as_of >= rule.disabled_from:
            reason = f"Discount rule '{rule.name}' is deactivated as of {rule.disabled_from}."
        elif rule.maximum_uses and used.get(rule.id, 0) >= rule.maximum_uses:
            reason = f"Discount rule '{rule.name}' has reached its maximum uses ({rule.maximum_uses})."
        elif not revision.valid_from <= as_of <= revision.valid_to:
            reason = f"Discount revision {revision.revision} is not valid on {as_of}."
        terms.append(Discount(revision_id=revision.id, rule_id=rule.id, name=f"{rule.name} (Rev {revision.revision})",
            scope=revision.scope, type=revision.type, product_ids=frozenset(products.get(revision.id, set())),
            amount=revision.amount, rate=revision.rate, minimum_purchase=revision.minimum_purchase,
            minimum_quantity=revision.minimum_quantity, ineligible_reason=reason))
    return terms
