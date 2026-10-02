"""Create or resolve a Symple One seller login after Amazon OAuth completes."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import User, UserKind, UserStatus
from app.schemas.auth import AuthUserOut
from app.services.amazon.seller_connection_service import find_seller_connection
from app.services.users import create_user


def seller_login_email(selling_partner_id: str) -> str:
    local = selling_partner_id.strip().lower()
    return f"{local}@sellers.sympleone.app"


def seller_display_name(selling_partner_id: str) -> str:
    partner = selling_partner_id.strip()
    suffix = partner[-6:] if len(partner) >= 6 else partner
    return f"Seller {suffix}"


@dataclass(frozen=True)
class SellerSessionAfterOAuth:
    access_token: str
    user: AuthUserOut
    new_account_email: str | None = None
    new_account_password: str | None = None


def _auth_user_out(user: User) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        email=user.email,
        name=user.full_name,
        role=user.kind.value,
    )


def establish_seller_session_after_oauth(
    db: Session,
    *,
    organization_id: str | None,
    selling_partner_id: str,
) -> SellerSessionAfterOAuth | None:
    """
    Ensure the Amazon connection is linked to a Symple user and return a JWT.

    When no user is linked yet, provisions a seller account and returns a one-time password.
    """
    connection = find_seller_connection(
        db,
        organization_id=organization_id,
        selling_partner_id=selling_partner_id,
    )
    if connection is None:
        return None

    new_password: str | None = None
    user: User | None = None
    if connection.user_id:
        user = db.get(User, connection.user_id)

    if user is None or user.deleted_at is not None:
        email = seller_login_email(selling_partner_id)
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if (
            existing is not None
            and existing.kind == UserKind.SELLER
            and existing.deleted_at is None
        ):
            user = existing
            connection.user_id = user.id
            db.commit()
        else:
            new_password = secrets.token_urlsafe(12)
            user = create_user(
                db,
                email=email,
                password=new_password,
                full_name=seller_display_name(selling_partner_id),
                kind=UserKind.SELLER,
            )
            connection.user_id = user.id
            db.commit()

    if user.status == UserStatus.SUSPENDED:
        return None

    token = create_access_token(user.id, extra={"kind": user.kind.value})
    return SellerSessionAfterOAuth(
        access_token=token,
        user=_auth_user_out(user),
        new_account_email=user.email if new_password else None,
        new_account_password=new_password,
    )
