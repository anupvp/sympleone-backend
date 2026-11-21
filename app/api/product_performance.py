import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.product_performance import (
    ProductPerformanceListOut,
    ProductPerformanceSummaryOut,
    ProductPerformanceSyncOut,
)
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.product_performance.query_service import (
    ProductPerformanceQueryError,
    build_summary,
    list_low_products,
    list_top_products,
)
from app.services.product_performance.sync_service import (
    ProductPerformanceSyncError,
    sync_product_performance_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/product-performance", tags=["product-performance"])


def _performance_seller(
    user: User,
    db: Session,
    sellerId: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, sellerId)


@router.post("/sync", response_model=ProductPerformanceSyncOut)
def post_product_performance_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
) -> ProductPerformanceSyncOut:
    try:
        payload = sync_product_performance_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_performance_seller(user, db, sellerId),
        )
        return ProductPerformanceSyncOut(**payload)
    except ProductPerformanceSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Product performance sync failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not sync product performance",
        ) from None


@router.get("/top", response_model=ProductPerformanceListOut)
def get_top_products(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
) -> ProductPerformanceListOut:
    try:
        payload = list_top_products(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_performance_seller(user, db, sellerId),
            limit=limit,
        )
        return ProductPerformanceListOut(**payload)
    except ProductPerformanceQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Top products failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load top products",
        ) from None


@router.get("/low", response_model=ProductPerformanceListOut)
def get_low_products(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
) -> ProductPerformanceListOut:
    try:
        payload = list_low_products(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_performance_seller(user, db, sellerId),
            limit=limit,
        )
        return ProductPerformanceListOut(**payload)
    except ProductPerformanceQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Low products failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load low-performing products",
        ) from None


@router.get("/summary", response_model=ProductPerformanceSummaryOut)
def get_product_performance_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
) -> ProductPerformanceSummaryOut:
    try:
        payload = build_summary(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_performance_seller(user, db, sellerId),
        )
        return ProductPerformanceSummaryOut(**payload)
    except ProductPerformanceQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Product performance summary failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load product performance summary",
        ) from None