from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public import SellerCountOut
from app.services.seller_admin import count_active_sellers

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/seller-count", response_model=SellerCountOut)
def get_seller_count(db: Session = Depends(get_db)) -> SellerCountOut:
    """Total active seller accounts (no auth — used on login marketing)."""
    return SellerCountOut(total=count_active_sellers(db))
