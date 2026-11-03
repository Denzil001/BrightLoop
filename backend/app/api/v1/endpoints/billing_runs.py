import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.contracts import created_location, ordering
from app.api.deps import get_current_db, require_role, verify_csrf, verify_origin
from app.db.session import SessionLocal
from app.models.billing import BillingOutcome, BillingRun
from app.models.users import User
from app.schemas.invoices import BillingRunCreate
from app.services.billing_runs import run_billing
from app.services.financial_calculator import PricingError
from app.services.scheduler import scheduler_status

router = APIRouter()


def get_billing_session_factory():
    return SessionLocal


def run_summary(run):
    return {"id": run.id, "as_of_date": run.as_of_date, "trigger": run.trigger,
            "retry_of_id": run.retry_of_id,
            "state": run.state, "started_at": run.started_at, "finished_at": run.finished_at,
            "summary": run.summary_counts}


@router.get("")
def list_runs(sort: str = Query("started_at", pattern="^(started_at|state|as_of_date)$"), descending: bool = True,
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_current_db), _: User = Depends(require_role(["ADMIN"]))):
    total = db.scalar(select(func.count()).select_from(BillingRun))
    runs = db.scalars(select(BillingRun).order_by(*ordering(sort, descending, {"started_at": BillingRun.started_at, "state": BillingRun.state, "as_of_date": BillingRun.as_of_date}, BillingRun.id))
                      .offset((page - 1) * page_size).limit(page_size))
    return {"items": [run_summary(run) for run in runs], "total": total, "page": page, "page_size": page_size,
            "scheduler": scheduler_status(db)}


@router.post("", status_code=201, dependencies=[Depends(verify_csrf), Depends(verify_origin)])
def create_run(response: Response, payload: BillingRunCreate, db: Session = Depends(get_current_db),
                user: User = Depends(require_role(["ADMIN"])), session_factory=Depends(get_billing_session_factory)):
    try:
        run_id = run_billing(payload.as_of_date, user.id, after_subscription_id=payload.after_subscription_id,
                             max_periods=payload.max_periods, session_factory=session_factory,
                             subscription_id=payload.subscription_id, retry_of_id=payload.retry_of_id)
    except PricingError as exc:
        raise HTTPException(422, str(exc)) from exc
    created_location(response, f"billing-runs/{run_id}")
    return run_summary(db.get(BillingRun, run_id))


@router.get("/{run_id}")
def get_run(run_id: uuid.UUID, sort: str = Query("created_at", pattern="^(created_at|period_start|state)$"), descending: bool = False,
             page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
             db: Session = Depends(get_current_db), _: User = Depends(require_role(["ADMIN"]))):
    run = db.get(BillingRun, run_id)
    if run is None:
        raise HTTPException(404, "Billing run not found.")
    query = select(BillingOutcome).where(BillingOutcome.run_id == run_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    outcomes = db.scalars(query.order_by(*ordering(sort, descending, {"created_at": BillingOutcome.created_at,
        "period_start": BillingOutcome.period_start, "state": BillingOutcome.state}, BillingOutcome.id))
                          .offset((page - 1) * page_size).limit(page_size))
    return {**run_summary(run), "outcomes": [{"id": outcome.id, "subscription_id": outcome.subscription_id,
        "period_start": outcome.period_start, "invoice_id": outcome.invoice_id, "state": outcome.state,
        "safe_error_code": outcome.safe_error_code} for outcome in outcomes], "total": total, "page": page, "page_size": page_size}
