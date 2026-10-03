from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import user_policy_codes
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import User, UserStatus
from app.schemas.auth import (
    AuthUserOut,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
)
from app.services.users import update_user_fields

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_user(user: User) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        email=user.email,
        name=user.full_name,
        role=user.kind.value,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
    token = create_access_token(user.id, extra={"kind": user.kind.value})
    return LoginResponse(accessToken=token, user=_auth_user(user))


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.full_name,
        role=user.kind.value,
        status=user.status.value,
        policies=sorted(user_policy_codes(db, user)),
    )


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"message": "Logged out"}


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangePasswordResponse:
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    update_user_fields(db, user, password=body.new_password)
    return ChangePasswordResponse(message="Password updated")
