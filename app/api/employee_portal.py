from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.schemas.employee_portal import EmployeeProfileOut, EmployeeSellerRowOut
from app.services.assignments import list_assigned_sellers
from app.services.seller_access_requests import create_access_request, list_active_sellers_catalog

router = APIRouter(prefix="/employee", tags=["employee-portal"])


def _require_employee(user: User) -> User:
    if user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=403, detail="Employee account required")
    return user


@router.get("/me", response_model=EmployeeProfileOut)
def employee_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmployeeProfileOut:
    user = _require_employee(user)
    manager_name = None
    if user.manager_id:
        manager = db.get(User, user.manager_id)
        if manager:
            manager_name = manager.full_name
    code = user.employee_code or user.id[:8].upper()
    return EmployeeProfileOut(
        id=user.id,
        full_name=user.full_name,
        employee_code=code,
        location=user.location,
        manager_name=manager_name,
        joined_at=user.created_at,
    )


@router.get("/sellers", response_model=list[EmployeeSellerRowOut])
def employee_sellers_catalog(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmployeeSellerRowOut]:
    user = _require_employee(user)
    rows = list_active_sellers_catalog(db, user)
    return [EmployeeSellerRowOut(**row) for row in rows]


@router.get("/assigned-sellers", response_model=list[EmployeeSellerRowOut])
def employee_assigned_sellers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmployeeSellerRowOut]:
    user = _require_employee(user)
    assigned = list_assigned_sellers(db, user.id)
    return [
        EmployeeSellerRowOut(
            id=s.id,
            full_name=s.full_name,
            status=s.status,
            has_dashboard_access=True,
            access_request_status=None,
        )
        for s in assigned
    ]


@router.post("/seller-access-requests/{seller_id}", status_code=201)
def request_seller_access(
    seller_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = _require_employee(user)
    row = create_access_request(db, user, seller_id)
    return {"id": row.id, "status": row.status.value}
