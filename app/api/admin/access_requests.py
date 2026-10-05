from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import User
from app.schemas.employee_portal import SellerAccessRequestOut
from app.services.seller_access_requests import (
    approve_request,
    list_pending_for_admin,
    reject_request,
)

router = APIRouter(prefix="/admin/seller-access-requests", tags=["admin-access-requests"])


@router.get("", response_model=list[SellerAccessRequestOut])
def list_access_requests(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SellerAccessRequestOut]:
    rows = list_pending_for_admin(db)
    return [SellerAccessRequestOut(**row) for row in rows]


@router.post("/{request_id}/approve", response_model=SellerAccessRequestOut)
def approve_access_request(
    request_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SellerAccessRequestOut:
    row = approve_request(db, admin, request_id)
    return SellerAccessRequestOut(**row)


@router.post("/{request_id}/reject", status_code=204)
def reject_access_request(
    request_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    reject_request(db, admin, request_id)
