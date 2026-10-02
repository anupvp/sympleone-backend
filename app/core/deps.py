from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    POLICY_AMAZON_SELLER_CONNECT,
    assert_user_active,
    user_has_policy,
)
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User, UserKind, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Send Authorization: Bearer <accessToken>.",
        )
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Use Bearer token.",
        )
    token = credentials.credentials.strip()
    if token.startswith("relaxed."):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Development mock token cannot access the API. "
                "Set VITE_AUTH_RELAXED=false and sign in via POST /api/auth/login."
            ),
        )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user when a valid Bearer token is sent; otherwise None."""
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        return None
    token = credentials.credentials.strip()
    if token.startswith("relaxed."):
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user = db.get(User, payload["sub"])
    if not user or user.deleted_at is not None:
        return None
    if user.status == UserStatus.SUSPENDED:
        return None
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.kind != UserKind.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Admin access required. Only Symple owner (admin) accounts "
                "can perform this action."
            ),
        )
    return user


def assert_user_may_start_amazon_connect(user: User, db: Session) -> None:
    """Admin, employees with amazon:seller:connect, or sellers (own account)."""
    if user.kind == UserKind.ADMIN:
        return
    if user.kind == UserKind.SELLER:
        return
    if user_has_policy(db, user, POLICY_AMAZON_SELLER_CONNECT):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


def require_amazon_seller_connect(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    assert_user_may_start_amazon_connect(user, db)
    return user


def require_policy(policy_code: str):
    def _checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        try:
            assert_user_active(user)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        if not user_has_policy(db, user, policy_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def ensure_employee(user: User) -> None:
    if user.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=400, detail="User is not an employee")


def ensure_seller(user: User) -> None:
    if user.kind != UserKind.SELLER:
        raise HTTPException(status_code=400, detail="User is not a seller")
