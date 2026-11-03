"""Reconstruct billable service segments from durable term/pause history."""
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.models.subscriptions import AgreementVersion, SubscriptionPause, SubscriptionTerm
from app.services.calendar import boundary


@dataclass(frozen=True)
class Period:
    term_id: UUID
    start: date
    end: date
    full_end: date

    @property
    def service_days(self):
        return (self.end - self.start).days

    @property
    def full_days(self):
        return (self.full_end - self.start).days


def periods(db, subscription_id):
    """Current state/cursor never removes eligible historical periods."""
    terms = db.scalars(select(SubscriptionTerm).where(SubscriptionTerm.subscription_id == subscription_id)
                       .order_by(SubscriptionTerm.sequence)).all()
    pauses = {}
    for pause in db.scalars(select(SubscriptionPause).join(SubscriptionTerm)
                           .where(SubscriptionTerm.subscription_id == subscription_id)
                           .order_by(SubscriptionPause.start_date, SubscriptionPause.id)):
        pauses.setdefault(pause.term_id, []).append(pause)
    for term in terms:
        start = term.start_date
        segments = []
        for pause in pauses.get(term.id, []):
            segments.append((start, min(pause.start_date, term.expiry_date)))
            start = pause.resumed_date
            if start is None:
                break
        if start is not None:
            segments.append((start, term.expiry_date))
        for anchor, end in segments:
            offset = 0
            while (start := boundary(anchor, term.interval, offset)) < end:
                full_end = boundary(anchor, term.interval, offset + 1)
                yield Period(term.id, start, min(end, full_end), full_end)
                offset += 1


def agreement_for_period(db, period):
    return db.scalar(select(AgreementVersion).where(AgreementVersion.term_id == period.term_id,
        AgreementVersion.state == "ACCEPTED", AgreementVersion.effective_from <= period.start)
        .order_by(AgreementVersion.effective_from.desc(), AgreementVersion.sequence.desc()).limit(1))
