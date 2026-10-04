from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.permissions import accessible_seller_ids
from app.database import get_db
from app.models import User, UserKind, UserStatus
from app.schemas.user import (
    AdminSellersOverviewOut,
    SellerCreate,
    SellerOut,
    SellerUpdate,
    UserOut,
)
from app.services.assignments import assign_sellers_to_employee
from app.services.seller_admin import (
    list_sellers_for_admin,
    seller_row_out,
    sellers_overview_counts,
)
from app.services.users import create_user, update_user_fields, user_to_out


def _get_seller(db: Session, seller_id: str) -> User | None:
    user = db.get(User, seller_id)
    if not user or user.kind != UserKind.SELLER or user.deleted_at is not None:
        return None
    return user


router = APIRouter(prefix="/admin/sellers", tags=["admin-sellers"])


@router.get("/overview", response_model=AdminSellersOverviewOut)
def sellers_overview(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSellersOverviewOut:
    rows = list_sellers_for_admin(db)
    return AdminSellersOverviewOut(
        counts=sellers_overview_counts(rows),
        sellers=[SellerOut(**r) for r in rows],
    )


@router.get("", response_model=list[SellerOut])
def list_sellers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SellerOut]:
    if user.kind == UserKind.ADMIN:
        rows = list_sellers_for_admin(db)
        return [SellerOut(**r) for r in rows]

    allowed = accessible_seller_ids(db, user)
    if not allowed:
        return []
    sellers = db.execute(select(User).where(User.id.in_(allowed))).scalars().all()
    return [SellerOut(**seller_row_out(db, s)) for s in sellers]


@router.post("", response_model=UserOut, status_code=201)
def create_seller(
    body: SellerCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        kind=UserKind.SELLER,
    )
    return UserOut(**user_to_out(db, user))


@router.patch("/{seller_id}", response_model=SellerOut)
def update_seller(
    seller_id: str,
    body: SellerUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SellerOut:
    user = _get_seller(db, seller_id)
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")
    user = update_user_fields(
        db,
        user,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        is_paid=body.is_paid,
    )
    return SellerOut(**seller_row_out(db, user))


@router.post("/{seller_id}/assign/{employee_id}", response_model=SellerOut)
def assign_seller_to_employee(
    seller_id: str,
    employee_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SellerOut:
    seller = _get_seller(db, seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    employee = db.get(User, employee_id)
    if not employee or employee.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    assign_sellers_to_employee(db, employee_id, [seller_id])
    db.commit()
    db.refresh(seller)
    return SellerOut(**seller_row_out(db, seller))


@router.post("/{seller_id}/suspend", response_model=UserOut)
def suspend_seller(
    seller_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = _get_seller(db, seller_id)
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")
    user.status = UserStatus.SUSPENDED
    db.commit()
    db.refresh(user)
    return UserOut(**user_to_out(db, user))


@router.post("/{seller_id}/activate", response_model=UserOut)
def activate_seller(
    seller_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = _get_seller(db, seller_id)
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")
    user.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return UserOut(**user_to_out(db, user))


@router.delete("/{seller_id}", status_code=204)
def delete_seller(
    seller_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, seller_id)
    if not user or user.kind != UserKind.SELLER or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Seller not found")
    user.deleted_at = datetime.now(UTC)
    db.commit()
