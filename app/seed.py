from sqlalchemy import select

from app.config import settings
from app.core.permissions import DEFAULT_POLICIES
from app.core.security import hash_password
from app.database import SessionLocal, engine, Base
from app.models import Policy, Role, RolePolicy, User, UserKind, UserStatus


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for code, description in DEFAULT_POLICIES:
            if not db.execute(select(Policy.id).where(Policy.code == code)).first():
                db.add(Policy(code=code, description=description))
        db.commit()

        admin = db.execute(
            select(User).where(User.email == settings.admin_email)
        ).scalar_one_or_none()
        if not admin:
            admin = User(
                email=settings.admin_email,
                full_name="Symple Owner",
                hashed_password=hash_password(settings.admin_password),
                kind=UserKind.ADMIN,
                status=UserStatus.ACTIVE,
            )
            db.add(admin)
            db.commit()

        if not db.execute(select(Role.id).where(Role.name == "Operations Manager")).first():
            role = Role(
                name="Operations Manager",
                description="Read assigned sellers and dashboard",
            )
            db.add(role)
            db.flush()
            policy_rows = db.execute(select(Policy)).scalars().all()
            pmap = {p.code: p.id for p in policy_rows}
            for code in ("dashboard:read", "products:read_assigned", "seller_accounts:read"):
                if code in pmap:
                    db.add(RolePolicy(role_id=role.id, policy_id=pmap[code]))
            db.commit()
    finally:
        db.close()
