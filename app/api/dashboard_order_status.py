import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.order_status import (
    OrderStatusOut,
    OrderStatusSyncOut,
    OrderStatusSyncStatusOut,
)
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.order_status.query_service import (
    OrderStatusQueryError,
    build_order_status_for_user,
    get_sync_status_for_user,
)
from app.services.order_status.sync_service import (
    OrderStatusSyncError,
    sync_dashboard_orders_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dashboard/order-status", tags=["dashboard-order-status"])


def _order_status_seller(
    user: User,
    db: Session,
    sellerId: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, sellerId)


@router.get("", response_model=OrderStatusOut)
def get_order_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
) -> OrderStatusOut:
    try:
        payload = build_order_status_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_order_status_seller(user, db, sellerId),
        )
        return OrderStatusOut(**payload)
    except OrderStatusQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Order status failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load order status",
        ) from None


@router.post("/sync", response_model=OrderStatusSyncOut)
def post_order_status_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
) -> OrderStatusSyncOut:
    try:
        payload = sync_dashboard_orders_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_order_status_seller(user, db, sellerId),
        )
        return OrderStatusSyncOut(**payload)
    except OrderStatusSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Order status sync failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not sync order status",
        ) from None


@router.get("/sync-status", response_model=OrderStatusSyncStatusOut)
def get_order_status_sync_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
) -> OrderStatusSyncStatusOut:
    try:
        payload = get_sync_status_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            seller=_order_status_seller(user, db, sellerId),
        )
        return OrderStatusSyncStatusOut(**payload)
    except OrderStatusQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Order status sync-status failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load sync status",
        ) from None