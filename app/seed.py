from sqlalchemy import inspect, select, text

from app.config import settings
from app.core.permissions import DEFAULT_POLICIES
from app.core.security import hash_password
from app.database import SessionLocal, engine, Base
from app.models import Policy, Role, RolePolicy, User, UserKind, UserStatus


def _ensure_appstore_oauth_columns() -> None:
    insp = inspect(engine)
    if "amazon_appstore_oauth_sessions" not in insp.get_table_names():
        return
    columns = {col["name"] for col in insp.get_columns("amazon_appstore_oauth_sessions")}
    if "organization_id" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE amazon_appstore_oauth_sessions ADD COLUMN organization_id VARCHAR(36)")
            )
    if "used_at" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE amazon_appstore_oauth_sessions ADD COLUMN used_at DATETIME")
            )


def _ensure_amazon_seller_auth_columns() -> None:
    insp = inspect(engine)
    if "amazon_seller_authorizations" not in insp.get_table_names():
        return
    columns = {col["name"] for col in insp.get_columns("amazon_seller_authorizations")}
    with engine.begin() as conn:
        if "refresh_token_ciphertext" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN refresh_token_ciphertext TEXT NOT NULL DEFAULT ''"
                )
            )
        if "status" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN status VARCHAR(32) DEFAULT 'active'"
                )
            )
        if "connected_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN connected_at DATETIME"
                )
            )
        if "last_authorized_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN last_authorized_at DATETIME"
                )
            )
        if "created_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN created_at DATETIME"
                )
            )
        if "updated_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE amazon_seller_authorizations "
                    "ADD COLUMN updated_at DATETIME"
                )
            )


def _ensure_user_columns() -> None:
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    columns = {col["name"] for col in insp.get_columns("users")}
    if "deleted_at" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN deleted_at DATETIME"))


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_user_columns()
    _ensure_appstore_oauth_columns()
    _ensure_amazon_seller_auth_columns()
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
