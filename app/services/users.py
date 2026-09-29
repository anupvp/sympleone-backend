from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Role, User, UserKind, UserRole, UserStatus


def effective_user_status(user: User) -> UserStatus:
    if user.deleted_at is not None:
        return UserStatus.DELETED
    return user.status


def seller_is_assignable(seller: User | None) -> bool:
    return (
        seller is not None
        and seller.kind == UserKind.SELLER
        and seller.deleted_at is None
    )


def _sync_user_roles(db: Session, user: User, role_ids: list[str]) -> None:
    if user.kind != UserKind.EMPLOYEE:
        return
    roles = db.execute(select(Role).where(Role.id.in_(role_ids))).scalars().all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=400, detail="One or more roles not found")
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def user_to_out(db: Session, user: User) -> dict:
    role_ids = []
    if user.kind == UserKind.EMPLOYEE:
        rows = db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id)).all()
        role_ids = [r[0] for r in rows]
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "kind": user.kind,
        "status": effective_user_status(user),
        "role_ids": role_ids,
    }


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    kind: UserKind,
    role_ids: list[str] | None = None,
) -> User:
    exists = db.execute(select(User.id).where(User.email == email)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        kind=kind,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    if role_ids:
        _sync_user_roles(db, user, role_ids)
    db.commit()
    db.refresh(user)
    return user


def update_user_fields(
    db: Session,
    user: User,
    *,
    email: str | None = None,
    full_name: str | None = None,
    password: str | None = None,
    role_ids: list[str] | None = None,
) -> User:
    if email and email != user.email:
        clash = db.execute(select(User.id).where(User.email == email)).first()
        if clash:
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = email
    if full_name:
        user.full_name = full_name
    if password:
        user.hashed_password = hash_password(password)
    if role_ids is not None:
        _sync_user_roles(db, user, role_ids)
    db.commit()
    db.refresh(user)
    return user
