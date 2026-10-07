import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.orders import OrdersListOut, OrderRowOut
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.orders.orders_service import OrdersServiceError, list_orders_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


def _orders_seller(
    user: User,
    db: Session,
    seller_id: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, seller_id)


@router.get("", response_model=OrdersListOut)
def get_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplace_id: str = Query(default="all", alias="marketplaceId"),
    created_after: str | None = Query(default=None, alias="CreatedAfter"),
    created_before: str | None = Query(default=None, alias="CreatedBefore"),
    date_from: str | None = Query(default=None, alias="dateFrom"),
    date_to: str | None = Query(default=None, alias="dateTo"),
    seller_id: str | None = Query(default=None, alias="sellerId"),
) -> OrdersListOut:
    seller = _orders_seller(user, db, seller_id)
    try:
        payload = list_orders_for_user(
            db,
            user,
            marketplace_id=marketplace_id,
            created_after=created_after,
            created_before=created_before,
            date_from=date_from,
            date_to=date_to,
            seller=seller,
        )
    except OrdersServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to load orders for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load orders from Amazon",
        ) from None

    return OrdersListOut(
        orders=[OrderRowOut(**row) for row in payload["orders"]],
        created_after=payload.get("created_after"),
        created_before=payload.get("created_before"),
    )
