"""Pure Decimal arithmetic shared by live previews and historical invoices."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from app.core.limits import MAX_MONEY


class PricingError(Exception):
    pass


def round_money(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) > MAX_MONEY:
        raise PricingError("The calculated amount exceeds the supported monetary range.")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Tax:
    id: UUID
    name: str
    rate: Decimal


@dataclass(frozen=True)
class Charge:
    ordinal: int
    kind: str
    product_id: UUID | None
    quantity: int
    unit_price: Decimal
    taxes: tuple[Tax, ...] = ()


@dataclass(frozen=True)
class Discount:
    revision_id: UUID
    rule_id: UUID
    name: str
    scope: str
    type: str
    product_ids: frozenset[UUID] = frozenset()
    amount: Decimal | None = None
    rate: Decimal | None = None
    minimum_purchase: Decimal | None = None
    minimum_quantity: int | None = None
    ineligible_reason: str | None = None


@dataclass
class CalculatedLine:
    ordinal: int
    subtotal: Decimal
    discount: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    allocations: dict[UUID, Decimal] = field(default_factory=dict)
    taxes: list[tuple[Tax, Decimal, Decimal]] = field(default_factory=list)

    @property
    def total(self):
        return self.subtotal - self.discount + self.tax


@dataclass
class Calculation:
    lines: list[CalculatedLine]
    applied: list[Discount]
    reasons: list[str]

    @property
    def subtotal(self):
        return sum((line.subtotal for line in self.lines), Decimal("0.00"))

    @property
    def discount(self):
        return sum((line.discount for line in self.lines), Decimal("0.00"))

    @property
    def tax(self):
        return sum((line.tax for line in self.lines), Decimal("0.00"))

    @property
    def total(self):
        return self.subtotal - self.discount + self.tax


def allocate_fixed(amount: Decimal, bases: dict[int, Decimal]) -> dict[int, Decimal]:
    """Largest remainder in integer minor units; ordinal resolves equal shares."""
    total = sum(bases.values(), Decimal("0.00"))
    cents = int(round_money(min(amount, total)) * 100)
    if not total:
        return {ordinal: Decimal("0.00") for ordinal in bases}
    shares = [(ordinal, Decimal(cents) * base / total) for ordinal, base in bases.items()]
    remainder = cents - sum(int(value) for _, value in shares)
    shares.sort(key=lambda item: (-(item[1] - int(item[1])), item[0]))
    return {ordinal: Decimal(int(value) + (index < remainder)) / 100
            for index, (ordinal, value) in enumerate(shares)}


def calculate(charges: list[Charge], discounts: list[Discount], seats: int,
              service_days: int = 1, full_days: int = 1) -> Calculation:
    if not 0 < service_days <= full_days or seats < 1:
        raise PricingError("Invalid service-period proration or seat quantity.")
    if len({line.ordinal for line in charges}) != len(charges):
        raise PricingError("Charge ordinals must be unique.")
    if len({rule.rule_id for rule in discounts}) != len(discounts):
        raise PricingError("A discount rule can only be assigned once.")
    if len(discounts) > 1 and any(rule.scope == "SUBSCRIPTION" for rule in discounts):
        raise PricingError("A whole-subscription discount cannot coexist with other discount rules.")
    result = Calculation([], [], [])
    for charge in charges:
        if charge.quantity < 1 or not charge.unit_price.is_finite() or charge.unit_price < 0:
            raise PricingError("Charges require positive quantities and non-negative finite prices.")
        amount = Decimal(charge.quantity) * charge.unit_price * service_days / full_days
        result.lines.append(CalculatedLine(charge.ordinal, round_money(amount)))
    by_ordinal = {line.ordinal: line for line in result.lines}
    occupied = set()
    for rule in discounts:
        eligible = [charge for charge in charges if by_ordinal[charge.ordinal].subtotal > 0
                    and ((rule.scope == "SUBSCRIPTION" and charge.kind != "INCLUDED")
                         or (rule.scope == "PRODUCT" and charge.kind == "ADDON" and charge.product_id in rule.product_ids))]
        ordinals = {charge.ordinal for charge in eligible}
        if occupied & ordinals:
            raise PricingError("Product discount rules overlap on the same charge line.")
        occupied |= ordinals  # ineligible assigned rules still cannot conceal overlap
        subtotal = sum((by_ordinal[n].subtotal for n in ordinals), Decimal("0.00"))
        quantity = seats if rule.scope == "SUBSCRIPTION" else sum(charge.quantity for charge in eligible)
        reason = rule.ineligible_reason
        if not reason and rule.minimum_quantity and quantity < rule.minimum_quantity:
            reason = f"Requires minimum quantity {rule.minimum_quantity} (got {quantity})."
        if not reason and rule.minimum_purchase and subtotal < rule.minimum_purchase:
            reason = f"Requires minimum purchase INR {rule.minimum_purchase} (eligible subtotal is {subtotal})."
        if not reason and not eligible:
            reason = "No eligible charge lines for this discount."
        if reason:
            result.reasons.append(reason)
            continue
        if rule.type == "FIXED":
            allocations = allocate_fixed(rule.amount, {n: by_ordinal[n].subtotal for n in ordinals})
        else:
            allocations = {n: min(by_ordinal[n].subtotal, round_money(by_ordinal[n].subtotal * rule.rate / 100)) for n in ordinals}
        result.applied.append(rule)
        for ordinal, amount in allocations.items():
            by_ordinal[ordinal].discount = amount
            by_ordinal[ordinal].allocations[rule.revision_id] = amount
    for charge in charges:
        line = by_ordinal[charge.ordinal]
        base = line.subtotal - line.discount
        for tax in charge.taxes:
            amount = round_money(base * tax.rate / 100)
            line.taxes.append((tax, base, amount))
            line.tax += amount
    if any(value >= Decimal("10000000000000000") for value in (result.subtotal, result.discount, result.tax, result.total)):
        raise PricingError("The calculated amount exceeds the supported monetary range.")
    return result
