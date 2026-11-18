import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.reports import FinancesReportOut
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.reports.finances_report_service import (
    FinancesReportError,
    build_finances_report_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_seller(
    user: User,
    db: Session,
    seller_id: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, seller_id)


@router.get("/finances", response_model=FinancesReportOut)
def get_finances_report(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    sellerId: str | None = Query(default=None),
) -> FinancesReportOut:
    try:
        payload = build_finances_report_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_report_seller(user, db, sellerId),
        )
        return FinancesReportOut(**payload)
    except FinancesReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to build finances report for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load finances report",
        ) from None