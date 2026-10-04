"""Resolve which seller account dashboard data should reflect."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import accessible_seller_ids
from app.models import User, UserKind


def resolve_dashboard_seller(
    db: Session,
    actor: User,
    seller_id: str | None,
) -> User:
    if actor.kind == UserKind.SELLER:
        return actor

    if actor.kind not in (UserKind.ADMIN, UserKind.EMPLOYEE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard is not available for this account type",
        )

    if not seller_id or not seller_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a seller account to view the dashboard",
        )

    sid = seller_id.strip()
    allowed = accessible_seller_ids(db, actor)
    if sid not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this seller account",
        )

    seller = db.get(User, sid)
    if not seller or seller.kind != UserKind.SELLER or seller.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Seller not found")
    return seller
