from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import user_policy_codes
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import User, UserStatus
from app.schemas.auth import AuthUserOut, LoginRequest, LoginResponse, MeResponse

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
