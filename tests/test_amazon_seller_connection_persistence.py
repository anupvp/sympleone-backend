"""Amazon seller connection persistence (model, migration, service, API safety)."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.secret_storage import decrypt_secret, encrypt_secret
from app.database import Base, engine
from app.models import AmazonConnection, AmazonConnectionStatus, AmazonSellerAuthorization
from app.seed import _ensure_amazon_seller_auth_columns, run_seed
from app.services.amazon.oauth_state import oauth_state_expires_at
from app.services.amazon.seller_connection_service import upsert_seller_connection
from tests.conftest import bearer_token

PARTNER = "A3Q9EXAMPLEID"
ORG_A = "org-11111111-1111-1111-1111-111111111111"


def _oauth_session_row(
    db: Session,
    *,
    organization_id: str | None = ORG_A,
    user_id: str | None = None,
):
    from app.models import AmazonAppstoreOAuthSession

    row = AmazonAppstoreOAuthSession(
        internal_state=f"state-{uuid.uuid4()}",
        amazon_state="amz",
        selling_partner_id=PARTNER,
        amazon_callback_uri="https://sellercentral.amazon.com/x",
        user_id=user_id,
        organization_id=organization_id,
        expires_at=oauth_state_expires_at(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_amazon_connection_is_seller_authorization_model() -> None:
    assert AmazonConnection is AmazonSellerAuthorization
    assert AmazonConnection.__tablename__ == "amazon_seller_authorizations"


def test_migration_ensures_seller_authorization_columns(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_amazon_seller_auth_columns()
    columns = {col["name"] for col in inspect(engine).get_columns("amazon_seller_authorizations")}
    assert {
        "id",
        "selling_partner_id",
        "user_id",
        "organization_id",
        "refresh_token_ciphertext",
        "status",
        "connected_at",
        "last_authorized_at",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_run_seed_creates_seller_authorization_table() -> None:
    run_seed()
    assert "amazon_seller_authorizations" in inspect(engine).get_table_names()


def test_unique_organization_and_selling_partner_id_enforced(db: Session) -> None:
    now = datetime.now(UTC)
    ciphertext = encrypt_secret("rt")
    first = AmazonSellerAuthorization(
        selling_partner_id=PARTNER,
        organization_id=ORG_A,
        refresh_token_ciphertext=ciphertext,
        status=AmazonConnectionStatus.ACTIVE,
        connected_at=now,
        last_authorized_at=now,
    )
    duplicate = AmazonSellerAuthorization(
        selling_partner_id=PARTNER,
        organization_id=ORG_A,
        refresh_token_ciphertext=ciphertext,
        status=AmazonConnectionStatus.ACTIVE,
        connected_at=now,
        last_authorized_at=now,
    )
    db.add(first)
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refresh_token_ciphertext_is_encrypted_not_plaintext(db: Session) -> None:
    plain = "Atzr|LongLivedRefreshTokenExample"
    conn = upsert_seller_connection(
        db,
        oauth_session=_oauth_session_row(db),
        refresh_token=plain,
    )
    db.commit()
    assert conn.refresh_token_ciphertext != plain
    assert decrypt_secret(conn.refresh_token_ciphertext) == plain


def test_connect_api_never_returns_refresh_token(client: TestClient, admin_user) -> None:
    from app.models import User

    user: User = admin_user
    response = client.post(
        "/api/amazon/connect",
        json={"marketplace_id": "A21TJRUUN4KGV"},
        headers=bearer_token(user.id, user.kind),
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"authorization_url"}
    assert "refresh_token" not in response.text
    assert "refresh_token_ciphertext" not in response.text
