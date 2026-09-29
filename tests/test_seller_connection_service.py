import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.secret_storage import decrypt_secret, encrypt_secret
from app.models import (
    AmazonAppstoreOAuthSession,
    AmazonConnectionStatus,
    AmazonSellerAuthorization,
)
from app.services.amazon.oauth_state import oauth_state_expires_at
from app.services.amazon.seller_connection_service import (
    find_seller_connection,
    upsert_seller_connection,
)

PARTNER = "A3Q9EXAMPLEID"
ORG_A = "org-11111111-1111-1111-1111-111111111111"


def _session(
    db: Session,
    *,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> AmazonAppstoreOAuthSession:
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


def test_upsert_creates_encrypted_connection(db: Session) -> None:
    oauth = _session(db, organization_id=ORG_A, user_id=None)
    conn = upsert_seller_connection(db, oauth_session=oauth, refresh_token="refresh-secret-1")
    db.commit()
    db.refresh(conn)

    assert conn.status == AmazonConnectionStatus.ACTIVE
    assert conn.selling_partner_id == PARTNER
    assert conn.organization_id == ORG_A
    assert conn.connected_at is not None
    assert conn.last_authorized_at is not None
    assert decrypt_secret(conn.refresh_token_ciphertext) == "refresh-secret-1"


def test_upsert_updates_existing_connection_without_duplicate(db: Session) -> None:
    oauth = _session(db, organization_id=ORG_A)
    upsert_seller_connection(db, oauth_session=oauth, refresh_token="token-v1")
    db.commit()

    first = find_seller_connection(db, organization_id=ORG_A, selling_partner_id=PARTNER)
    assert first is not None
    first_connected = first.connected_at

    upsert_seller_connection(db, oauth_session=oauth, refresh_token="token-v2")
    db.commit()

    count = db.execute(
        select(func.count()).select_from(AmazonSellerAuthorization).where(
            AmazonSellerAuthorization.organization_id == ORG_A,
            AmazonSellerAuthorization.selling_partner_id == PARTNER,
        )
    ).scalar_one()
    assert count == 1

    updated = find_seller_connection(db, organization_id=ORG_A, selling_partner_id=PARTNER)
    assert updated is not None
    assert decrypt_secret(updated.refresh_token_ciphertext) == "token-v2"
    assert updated.connected_at == first_connected
    assert updated.last_authorized_at >= first.last_authorized_at


def test_different_organizations_allow_same_selling_partner_id(db: Session) -> None:
    org_b = "org-22222222-2222-2222-2222-222222222222"
    upsert_seller_connection(
        db,
        oauth_session=_session(db, organization_id=ORG_A),
        refresh_token="t1",
    )
    upsert_seller_connection(
        db,
        oauth_session=_session(db, organization_id=org_b),
        refresh_token="t2",
    )
    db.commit()

    rows = db.execute(select(AmazonSellerAuthorization)).scalars().all()
    assert len(rows) == 2
