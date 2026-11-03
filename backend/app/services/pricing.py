from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan, PlanItem, Product, ProductVariant
from app.models.taxes import PlanTax, ProductTax, TaxRule
from app.schemas.pricing import (
    PricingLineBreakdown,
    PricingLineInput,
    PricingPreviewRequest,
    PricingPreviewResponse,
    PricingTaxBreakdown,
)

from app.services.financial_calculator import Charge, Tax, calculate, round_money, PricingError
from app.services.discount_context import resolve_revisions, load_terms


class PricingService:
    @staticmethod
    def calculate_pricing(
        db: Session,
        request: PricingPreviewRequest,
    ) -> PricingPreviewResponse:
        as_of = request.as_of_date or get_business_today()

        # 1. Fetch and validate Plan
        plan = db.scalar(select(Plan).where(Plan.id == request.plan_id))
        if not plan:
            raise PricingError(f"Plan with id '{request.plan_id}' not found.")
        if not plan.active:
            raise PricingError(f"Plan '{plan.name}' is archived/inactive.")

        # Plan availability for the supplied business date
        if plan.available_from and as_of < plan.available_from:
            raise PricingError(
                f"Plan '{plan.name}' is not available until {plan.available_from} (as of date: {as_of})."
            )
        if plan.available_to and as_of > plan.available_to:
            raise PricingError(
                f"Plan '{plan.name}' is no longer available as of {as_of} (expired {plan.available_to})."
            )

        if request.seat_quantity < plan.minimum_seats:
            raise PricingError(
                f"Seat quantity ({request.seat_quantity}) cannot be less than plan minimum ({plan.minimum_seats})."
            )

        # Plan base charge and excess seats
        base_fee = round_money(plan.base_fee)
        excess_seats = max(0, request.seat_quantity - plan.minimum_seats)
        extra_seat_price = round_money(plan.extra_seat_unit_price)
        excess_seat_amount = round_money(Decimal(excess_seats) * extra_seat_price)

        # Plan taxes
        plan_taxes = db.scalars(
            select(TaxRule)
            .join(PlanTax, PlanTax.tax_rule_id == TaxRule.id)
            .where(PlanTax.plan_id == plan.id, TaxRule.active.is_(True))
        ).all()

        lines_breakdown: List[PricingLineBreakdown] = []
        ordinal = 1

        # Line 1: Plan base fee (standardized to PLAN_FEE matching agreement_lines)
        lines_breakdown.append(
            PricingLineBreakdown(
                ordinal=ordinal,
                line_kind="PLAN_FEE",
                description=f"{plan.name} (Base Fee, up to {plan.minimum_seats} seats)",
                product_id=None,
                variant_id=None,
                quantity=1,
                unit_price=str(base_fee),
                subtotal=str(base_fee),
                discount_amount="0.00",
                discounted_subtotal=str(base_fee),
                tax_amount="0.00",
                total=str(base_fee),
                tax_rates=[t.rate for t in plan_taxes],
            )
        )
        ordinal += 1

        # Line 2: Excess seats (if any)
        if excess_seats > 0:
            lines_breakdown.append(
                PricingLineBreakdown(
                    ordinal=ordinal,
                    line_kind="EXCESS_SEATS",
                    description=f"Additional Seats ({excess_seats} excess seats)",
                    product_id=None,
                    variant_id=None,
                    quantity=excess_seats,
                    unit_price=str(extra_seat_price),
                    subtotal=str(excess_seat_amount),
                    discount_amount="0.00",
                    discounted_subtotal=str(excess_seat_amount),
                    tax_amount="0.00",
                    total=str(excess_seat_amount),
                    tax_rates=[t.rate for t in plan_taxes],
                )
            )
            ordinal += 1

        # 2. Process product lines (included items and add-ons)
        line_taxes_map: Dict[int, List[TaxRule]] = {
            1: list(plan_taxes),
        }
        if excess_seats > 0:
            line_taxes_map[2] = list(plan_taxes)

        # Build plan included entitlements lookup
        plan_items = db.scalars(
            select(PlanItem).where(PlanItem.plan_id == plan.id)
        ).all()
        plan_included_limits: Dict[Tuple[uuid.UUID, Optional[uuid.UUID]], int] = {
            (pi.product_id, pi.variant_id): pi.included_quantity for pi in plan_items
        }
        accumulated_included: Dict[Tuple[uuid.UUID, Optional[uuid.UUID]], int] = {}

        for line_input in request.lines:
            product = db.scalar(select(Product).where(Product.id == line_input.product_id))
            if not product:
                raise PricingError(f"Product with id '{line_input.product_id}' not found.")
            if not product.active:
                raise PricingError(f"Product '{product.name}' is archived/inactive.")

            variant_name = None
            variant_adjustment = Decimal("0.00")
            if line_input.variant_id:
                variant = db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.id == line_input.variant_id,
                        ProductVariant.product_id == product.id,
                    )
                )
                if not variant:
                    raise PricingError(
                        f"Variant with id '{line_input.variant_id}' not found on product '{product.name}'."
                    )
                if not variant.active:
                    raise PricingError(f"Variant '{variant.name}' is archived/inactive.")
                variant_name = variant.name
                variant_adjustment = round_money(variant.price_adjustment)

            desc = product.name + (f" ({variant_name})" if variant_name else "")

            if line_input.line_kind == "INCLUDED":
                # Validate against plan included items
                item_key = (line_input.product_id, line_input.variant_id)
                if item_key not in plan_included_limits:
                    raise PricingError(
                        f"Item '{desc}' is not an included entitlement for plan '{plan.name}'. Fabricated entitlements are rejected."
                    )
                new_qty = accumulated_included.get(item_key, 0) + line_input.quantity
                max_qty = plan_included_limits[item_key]
                if new_qty > max_qty:
                    raise PricingError(
                        f"Requested included quantity ({new_qty}) for '{desc}' exceeds plan '{plan.name}' limit ({max_qty}). Excess quantity must be billed as paid add-ons."
                    )
                accumulated_included[item_key] = new_qty

                # Included items are zero incremental charge
                lines_breakdown.append(
                    PricingLineBreakdown(
                        ordinal=ordinal,
                        line_kind="INCLUDED",
                        description=f"[Included] {desc}",
                        product_id=product.id,
                        variant_id=line_input.variant_id,
                        quantity=line_input.quantity,
                        unit_price="0.00",
                        subtotal="0.00",
                        discount_amount="0.00",
                        discounted_subtotal="0.00",
                        tax_amount="0.00",
                        total="0.00",
                        tax_rates=[],
                    )
                )
                line_taxes_map[ordinal] = []
            else:
                # Paid add-on line
                standard_unit_price = round_money(product.sales_price + variant_adjustment)
                if line_input.agreed_unit_price is not None:
                    unit_price = round_money(line_input.agreed_unit_price)
                    if unit_price != standard_unit_price:
                        if not line_input.override_reason or not line_input.override_reason.strip():
                            raise PricingError(
                                f"Negotiated override price ({unit_price}) for '{desc}' differs from standard catalog price ({standard_unit_price}) but no override_reason was provided."
                            )
                else:
                    unit_price = standard_unit_price

                if unit_price < Decimal("0.00"):
                    raise PricingError(
                        f"Effective unit price for '{desc}' cannot be negative: {unit_price}"
                    )

                subtotal = round_money(Decimal(line_input.quantity) * unit_price)

                prod_taxes = db.scalars(
                    select(TaxRule)
                    .join(ProductTax, ProductTax.tax_rule_id == TaxRule.id)
                    .where(ProductTax.product_id == product.id, TaxRule.active.is_(True))
                ).all()

                lines_breakdown.append(
                    PricingLineBreakdown(
                        ordinal=ordinal,
                        line_kind="ADDON",
                        description=desc,
                        product_id=product.id,
                        variant_id=line_input.variant_id,
                        quantity=line_input.quantity,
                        unit_price=str(unit_price),
                        subtotal=str(subtotal),
                        discount_amount="0.00",
                        discounted_subtotal=str(subtotal),
                        tax_amount="0.00",
                        total=str(subtotal),
                        tax_rates=[t.rate for t in prod_taxes],
                    )
                )
                line_taxes_map[ordinal] = list(prod_taxes)

            ordinal += 1

        # The exact same calculator consumes live catalog context here and frozen
        # agreement context in billing. No financial arithmetic lives in routes.
        revisions = resolve_revisions(db,
            list(request.discount_ids) + ([request.discount_id] if request.discount_id else []),
            list(request.discount_revision_ids) + ([request.discount_revision_id] if request.discount_revision_id else []), as_of)
        terms = load_terms(db, revisions, as_of)
        charges = [Charge(line.ordinal, line.line_kind, line.product_id, line.quantity, Decimal(line.unit_price),
                          tuple(Tax(t.id, t.name, t.rate) for t in line_taxes_map.get(line.ordinal, [])))
                   for line in lines_breakdown]
        result = calculate(charges, terms, request.seat_quantity)
        taxes = {}
        for line, calculated in zip(lines_breakdown, result.lines):
            line.subtotal = str(calculated.subtotal)
            line.discount_amount = str(calculated.discount)
            line.discounted_subtotal = str(calculated.subtotal - calculated.discount)
            line.tax_amount = str(calculated.tax)
            line.total = str(calculated.total)
            for tax, base, amount in calculated.taxes:
                if tax.id not in taxes:
                    taxes[tax.id] = [tax, Decimal("0.00"), Decimal("0.00")]
                taxes[tax.id][1] += base
                taxes[tax.id][2] += amount
        applied = [discount.revision_id for discount in result.applied]
        return PricingPreviewResponse(
            plan_name=plan.name, base_fee=str(base_fee), minimum_seats=plan.minimum_seats,
            seat_quantity=request.seat_quantity, excess_seats=excess_seats,
            extra_seat_unit_price=str(extra_seat_price), excess_seat_amount=str(excess_seat_amount),
            subtotal=str(result.subtotal), total_discount=str(result.discount),
            taxable_amount=str(result.subtotal - result.discount), total_tax=str(result.tax), total=str(result.total),
            lines=lines_breakdown, tax_breakdown=[PricingTaxBreakdown(tax_rule_id=tax.id, name=tax.name,
                rate=tax.rate, taxable_base=str(base), tax_amount=str(amount)) for tax, base, amount in taxes.values()],
            discount_applied=", ".join(discount.name for discount in result.applied) or None,
            discount_revision_id=applied[0] if applied else None,
            discount_ineligible_reason="; ".join(result.reasons) or None,
            assigned_discount_revision_ids=[revision.id for revision in revisions],
            applied_discount_revision_ids=applied,
        )
