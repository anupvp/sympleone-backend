import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# File-backed SQLite so connections share schema (in-memory sqlite:// needs StaticPool).
os.environ["SYMPLEONE_DATABASE_URL"] = "sqlite:///./.pytest_sympleone.db"
os.environ.setdefault("AMAZON_APP_ID", "amzn1.sellerapps.app.testappid")
os.environ.setdefault("AMAZON_REDIRECT_URI", "https://example.com/api/amazon/oauth/callback")
os.environ.setdefault("AMAZON_CLIENT_SECRET", "test-client-secret-do-not-log")

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine, get_db
from app.main import app
from app.models import Policy, Role, RolePolicy, User, UserKind, UserRole, UserStatus


def override_get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _reset_db() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    settings.amazon_app_id = os.environ["AMAZON_APP_ID"]
    settings.amazon_redirect_uri = os.environ["AMAZON_REDIRECT_URI"]
    settings.amazon_client_secret = os.environ["AMAZON_CLIENT_SECRET"]
    settings.amazon_authorize_version = "beta"
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def bearer_token(user_id: str, kind: UserKind = UserKind.EMPLOYEE) -> dict[str, str]:
    token = create_access_token(user_id, extra={"kind": kind.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db: Session) -> User:
    user = User(
        email="admin@test.com",
        full_name="Admin",
        hashed_password=hash_password("password"),
        kind=UserKind.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def connect_policy(db: Session) -> Policy:
    policy = Policy(code="amazon:seller:connect", description="Connect Amazon sellers")
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@pytest.fixture
def employee_with_connect(db: Session, connect_policy: Policy) -> User:
    role = Role(name="Amazon Connector", description="Can connect sellers")
    db.add(role)
    db.flush()
    db.add(RolePolicy(role_id=role.id, policy_id=connect_policy.id))
    user = User(
        email="connector@test.com",
        full_name="Connector",
        hashed_password=hash_password("password"),
        kind=UserKind.EMPLOYEE,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def employee_without_connect(db: Session) -> User:
    user = User(
        email="staff@test.com",
        full_name="Staff",
        hashed_password=hash_password("password"),
        kind=UserKind.EMPLOYEE,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def seller_user(db: Session) -> User:
    user = User(
        email="seller@test.com",
        full_name="Seller",
        hashed_password=hash_password("password"),
        kind=UserKind.SELLER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
