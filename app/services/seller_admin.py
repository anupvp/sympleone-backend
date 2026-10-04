"""Admin seller list helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EmployeeSellerAssignment, User, UserKind
from app.services.users import effective_user_status, user_to_out


def _assigned_employee_names(db: Session, seller_id: str) -> list[str]:
    rows = db.execute(
        select(User.full_name)
        .join(
            EmployeeSellerAssignment,
            EmployeeSellerAssignment.employee_id == User.id,
        )
        .where(EmployeeSellerAssignment.seller_id == seller_id)
    ).all()
    return [r[0] for r in rows]


def seller_row_out(db: Session, seller: User) -> dict:
    base = user_to_out(db, seller)
    employees = _assigned_employee_names(db, seller.id)
    return {
        **base,
        "is_paid": bool(seller.is_paid),
        "is_assigned": len(employees) > 0,
        "assigned_employees": employees,
    }


def count_active_sellers(db: Session) -> int:
    total = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.kind == UserKind.SELLER, User.deleted_at.is_(None))
    )
    return int(total or 0)


def list_sellers_for_admin(db: Session) -> list[dict]:
    sellers = db.execute(
        select(User).where(User.kind == UserKind.SELLER, User.deleted_at.is_(None))
    ).scalars().all()
    return [seller_row_out(db, s) for s in sellers]


def sellers_overview_counts(rows: list[dict]) -> dict[str, int]:
    total = len(rows)
    assigned = sum(1 for r in rows if r["is_assigned"])
    paid = sum(1 for r in rows if r["is_paid"])
    return {
        "total": total,
        "assigned": assigned,
        "unassigned": total - assigned,
        "paid": paid,
        "unpaid": total - paid,
    }
