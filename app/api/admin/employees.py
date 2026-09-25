from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import EmployeeSellerAssignment, User, UserKind, UserStatus
from app.schemas.group import AssignSellersRequest
from app.schemas.user import EmployeeCreate, EmployeeUpdate, UserOut
from app.services.users import create_user, update_user_fields, user_to_out

router = APIRouter(prefix="/admin/employees", tags=["admin-employees"])


@router.get("", response_model=list[UserOut])
def list_employees(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    users = db.execute(select(User).where(User.kind == UserKind.EMPLOYEE)).scalars().all()
    return [UserOut(**user_to_out(db, u)) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_employee(
    body: EmployeeCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        kind=UserKind.EMPLOYEE,
        role_ids=body.role_ids,
    )
    return UserOut(**user_to_out(db, user))


@router.patch("/{employee_id}", response_model=UserOut)
def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, employee_id)
    if not user or user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    user = update_user_fields(
        db,
        user,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role_ids=body.role_ids,
    )
    return UserOut(**user_to_out(db, user))


@router.post("/{employee_id}/suspend", response_model=UserOut)
def suspend_employee(
    employee_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, employee_id)
    if not user or user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.status = UserStatus.SUSPENDED
    db.commit()
    db.refresh(user)
    return UserOut(**user_to_out(db, user))


@router.post("/{employee_id}/activate", response_model=UserOut)
def activate_employee(
    employee_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, employee_id)
    if not user or user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.status = UserStatus.ACTIVE
    db.commit()
    db.refresh(user)
    return UserOut(**user_to_out(db, user))


@router.delete("/{employee_id}", status_code=204)
def delete_employee(
    employee_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, employee_id)
    if not user or user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(user)
    db.commit()


@router.get("/{employee_id}/sellers", response_model=list[UserOut])
def list_assigned_sellers(
    employee_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    employee = db.get(User, employee_id)
    if not employee or employee.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    rows = db.execute(
        select(User)
        .join(EmployeeSellerAssignment, EmployeeSellerAssignment.seller_id == User.id)
        .where(EmployeeSellerAssignment.employee_id == employee_id)
    ).scalars().all()
    return [UserOut(**user_to_out(db, s)) for s in rows]


@router.post("/{employee_id}/sellers", response_model=list[UserOut])
def assign_sellers(
    employee_id: str,
    body: AssignSellersRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    employee = db.get(User, employee_id)
    if not employee or employee.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    for seller_id in body.seller_ids:
        seller = db.get(User, seller_id)
        if not seller or seller.kind != UserKind.SELLER:
            raise HTTPException(status_code=400, detail=f"Invalid seller: {seller_id}")
        exists = db.execute(
            select(EmployeeSellerAssignment.id).where(
                EmployeeSellerAssignment.employee_id == employee_id,
                EmployeeSellerAssignment.seller_id == seller_id,
            )
        ).first()
        if not exists:
            db.add(EmployeeSellerAssignment(employee_id=employee_id, seller_id=seller_id))
    db.commit()
    rows = db.execute(
        select(User)
        .join(EmployeeSellerAssignment, EmployeeSellerAssignment.seller_id == User.id)
        .where(EmployeeSellerAssignment.employee_id == employee_id)
    ).scalars().all()
    return [UserOut(**user_to_out(db, s)) for s in rows]


@router.delete("/{employee_id}/sellers/{seller_id}", status_code=204)
def remove_seller_assignment(
    employee_id: str,
    seller_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    row = db.execute(
        select(EmployeeSellerAssignment).where(
            EmployeeSellerAssignment.employee_id == employee_id,
            EmployeeSellerAssignment.seller_id == seller_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(row)
    db.commit()
