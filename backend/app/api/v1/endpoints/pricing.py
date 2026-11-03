from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_db, require_role, verify_csrf
from app.models.users import User
from app.schemas.pricing import PricingPreviewRequest, PricingPreviewResponse
from app.services.pricing import PricingError, PricingService

router = APIRouter()


@router.post("/preview", response_model=PricingPreviewResponse, dependencies=[Depends(verify_csrf)])
def preview_pricing(
    payload: PricingPreviewRequest,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    try:
        return PricingService.calculate_pricing(db, payload)
    except PricingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
