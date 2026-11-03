import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_db, get_current_user, require_role
from app.models.users import User
from app.services import reporting as service

router = APIRouter()


@router.get("/dashboard")
def dashboard(date_from: date | None = None, date_to: date | None = None,
                db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    return service.dashboard(db, user, date_from, date_to)


@router.get("/reports/summary")
def summary(date_from: date | None = None, date_to: date | None = None,
              customer_id: uuid.UUID | None = None, plan_id: uuid.UUID | None = None,
              db: Session = Depends(get_current_db), user: User = Depends(require_role(["ADMIN"]))):
    return service.summary(db, user, date_from, date_to, customer_id, plan_id)


@router.get("/reports/details")
def details(view: Literal["receipts", "outstanding", "overdue", "active"] = "receipts",
              date_from: date | None = None, date_to: date | None = None,
              customer_id: uuid.UUID | None = None, plan_id: uuid.UUID | None = None,
              sort: str = Query("date", pattern="^(date|amount|number|customer)$"), descending: bool | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_current_db), user: User = Depends(require_role(["ADMIN"]))):
    return service.report_details(db, user, view, date_from, date_to, customer_id, plan_id, page, page_size, sort, descending)
