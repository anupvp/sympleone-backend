from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import accessible_seller_ids
from app.models import SellerAccessRequest, SellerAccessRequestStatus, User, UserKind, UserStatus
from app.services.assignments import assign_sellers_to_employee


def _active_seller(db: Session, seller_id: str) -> User | None:
    seller = db.get(User, seller_id)
    if not seller or seller.kind != UserKind.SELLER or seller.deleted_at is not None:
        return None
    return seller


def list_active_sellers_catalog(db: Session, employee: User) -> list[dict]:
    allowed = accessible_seller_ids(db, employee)
    sellers = db.execute(
        select(User).where(
            User.kind == UserKind.SELLER,
            User.deleted_at.is_(None),
            User.status == UserStatus.ACTIVE,
        )
    ).scalars().all()

    pending = db.execute(
        select(SellerAccessRequest).where(
            SellerAccessRequest.employee_id == employee.id,
            SellerAccessRequest.status == SellerAccessRequestStatus.PENDING,
        )
    ).scalars().all()
    pending_by_seller = {row.seller_id: row.status.value for row in pending}

    rows: list[dict] = []
    for seller in sellers:
        access_status = pending_by_seller.get(seller.id)
        rows.append(
            {
                "id": seller.id,
                "full_name": seller.full_name,
                "status": seller.status.value,
                "has_dashboard_access": seller.id in allowed,
                "access_request_status": access_status,
            }
        )
    rows.sort(key=lambda r: r["full_name"].lower())
    return rows


def create_access_request(db: Session, employee: User, seller_id: str) -> SellerAccessRequest:
    if employee.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=403, detail="Only employees can request seller access")

    seller = _active_seller(db, seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    if seller_id in accessible_seller_ids(db, employee):
        raise HTTPException(status_code=400, detail="You already have access to this seller")

    existing = db.execute(
        select(SellerAccessRequest).where(
            SellerAccessRequest.employee_id == employee.id,
            SellerAccessRequest.seller_id == seller_id,
            SellerAccessRequest.status == SellerAccessRequestStatus.PENDING,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    row = SellerAccessRequest(
        employee_id=employee.id,
        seller_id=seller_id,
        status=SellerAccessRequestStatus.PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_pending_for_admin(db: Session) -> list[dict]:
    return _list_pending_requests(db)


def _list_pending_requests(db: Session) -> list[dict]:
    pending = db.execute(
        select(SellerAccessRequest).where(
            SellerAccessRequest.status == SellerAccessRequestStatus.PENDING
        )
    ).scalars().all()
    out: list[dict] = []
    for req in pending:
        employee = db.get(User, req.employee_id)
        seller = db.get(User, req.seller_id)
        if not employee or not seller:
            continue
        out.append(
            {
                "id": req.id,
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "seller_id": seller.id,
                "seller_name": seller.full_name,
                "status": req.status.value,
                "created_at": req.created_at,
            }
        )
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


def approve_request(db: Session, admin: User, request_id: str) -> dict:
    req = db.get(SellerAccessRequest, request_id)
    if not req or req.status != SellerAccessRequestStatus.PENDING:
        raise HTTPException(status_code=404, detail="Access request not found")

    assign_sellers_to_employee(db, req.employee_id, [req.seller_id])
    req.status = SellerAccessRequestStatus.APPROVED
    req.resolved_at = datetime.now(UTC)
    req.resolved_by_id = admin.id
    db.commit()
    employee = db.get(User, req.employee_id)
    seller = db.get(User, req.seller_id)
    return {
        "id": req.id,
        "employee_id": req.employee_id,
        "employee_name": employee.full_name if employee else "",
        "seller_id": req.seller_id,
        "seller_name": seller.full_name if seller else "",
        "status": req.status.value,
        "created_at": req.created_at,
    }


def reject_request(db: Session, admin: User, request_id: str) -> None:
    req = db.get(SellerAccessRequest, request_id)
    if not req or req.status != SellerAccessRequestStatus.PENDING:
        raise HTTPException(status_code=404, detail="Access request not found")
    req.status = SellerAccessRequestStatus.REJECTED
    req.resolved_at = datetime.now(UTC)
    req.resolved_by_id = admin.id
    db.commit()


def pending_access_request_count(db: Session) -> int:
    return len(
        db.execute(
            select(SellerAccessRequest.id).where(
                SellerAccessRequest.status == SellerAccessRequestStatus.PENDING
            )
        ).all()
    )
