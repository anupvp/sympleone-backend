import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.inventory import FbaInventoryOut
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.inventory.fba_inventory_service import (
    FbaInventoryError,
    build_fba_inventory_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _inventory_seller(
    user: User,
    db: Session,
    seller_id: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, seller_id)


@router.get("/fba", response_model=FbaInventoryOut)
def get_fba_inventory(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
) -> FbaInventoryOut:
    try:
        payload = build_fba_inventory_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            seller=_inventory_seller(user, db, sellerId),
        )
        return FbaInventoryOut(**payload)
    except FbaInventoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to build FBA inventory for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load FBA inventory",
        ) from None