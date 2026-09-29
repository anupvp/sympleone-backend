from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeSellerAssignment, User
from app.schemas.user import AssignedSellerSummary
from app.services.users import effective_user_status, seller_is_assignable


def list_assigned_sellers(db: Session, employee_id: str) -> list[AssignedSellerSummary]:
    rows = db.execute(
        select(User)
        .join(EmployeeSellerAssignment, EmployeeSellerAssignment.seller_id == User.id)
        .where(EmployeeSellerAssignment.employee_id == employee_id)
    ).scalars().all()
    return [
        AssignedSellerSummary(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            status=effective_user_status(u),
        )
        for u in rows
    ]


def assign_sellers_to_employee(db: Session, employee_id: str, seller_ids: list[str]) -> None:
    for seller_id in seller_ids:
        seller = db.get(User, seller_id)
        if not seller_is_assignable(seller):
            continue
        exists = db.execute(
            select(EmployeeSellerAssignment.id).where(
                EmployeeSellerAssignment.employee_id == employee_id,
                EmployeeSellerAssignment.seller_id == seller_id,
            )
        ).first()
        if not exists:
            db.add(EmployeeSellerAssignment(employee_id=employee_id, seller_id=seller_id))
