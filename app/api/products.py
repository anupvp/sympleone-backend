import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.products import ProductListingRowOut, ProductSummaryOut, ProductsPageOut
from app.services.dashboard.context import resolve_dashboard_seller
from app.services.products.products_service import ProductsServiceError, list_products_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/products", tags=["products"])


def _products_seller(
    user: User,
    db: Session,
    seller_id: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, seller_id)


@router.get("", response_model=ProductsPageOut)
def get_products(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    marketplaceId: str = Query(default="all"),
    sellerId: str | None = Query(default=None),
) -> ProductsPageOut:
    seller = _products_seller(user, db, sellerId)
    try:
        payload = list_products_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            seller=seller,
        )
    except ProductsServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to load products for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load products from Amazon",
        ) from None

    summary_raw = payload.get("summary") or {}
    return ProductsPageOut(
        marketplace_id=str(payload.get("marketplace_id") or ""),
        summary=ProductSummaryOut(
            total=int(summary_raw.get("total") or 0),
            active=int(summary_raw.get("active") or 0),
            inactive=int(summary_raw.get("inactive") or 0),
            out_of_stock=int(summary_raw.get("out_of_stock") or 0),
            draft=int(summary_raw.get("draft") or 0),
            suppressed=int(summary_raw.get("suppressed") or 0),
        ),
        products=[ProductListingRowOut(**row) for row in payload.get("products") or []],
    )