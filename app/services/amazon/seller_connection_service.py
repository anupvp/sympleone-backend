"""Persist Amazon SP-API seller connections and encrypted refresh tokens (server-side only)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secret_storage import encrypt_secret
from app.models import AmazonAppstoreOAuthSession, AmazonSellerAuthorization, AmazonConnectionStatus

logger = logging.getLogger(__name__)


def find_seller_connection(
    db: Session,
    *,
    organization_id: str | None,
    selling_partner_id: str,
) -> AmazonSellerAuthorization | None:
    stmt = select(AmazonSellerAuthorization).where(
        AmazonSellerAuthorization.selling_partner_id == selling_partner_id
    )
    if organization_id is None:
        stmt = stmt.where(AmazonSellerAuthorization.organization_id.is_(None))
    else:
        stmt = stmt.where(AmazonSellerAuthorization.organization_id == organization_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert_seller_connection(
    db: Session,
    *,
    oauth_session: AmazonAppstoreOAuthSession | None = None,
    refresh_token: str,
    user_id: str | None = None,
    organization_id: str | None = None,
    selling_partner_id: str | None = None,
) -> AmazonSellerAuthorization:
    """
    Encrypt and store refresh_token at rest; create or update (organization_id, selling_partner_id).
    """
    if oauth_session is not None:
        organization_id = oauth_session.organization_id
        selling_partner_id = oauth_session.selling_partner_id
        user_id = oauth_session.user_id
    if not selling_partner_id:
        raise ValueError("selling_partner_id is required")

    ciphertext = encrypt_secret(refresh_token)
    now = datetime.now(UTC)

    existing = find_seller_connection(
        db,
        organization_id=organization_id,
        selling_partner_id=selling_partner_id,
    )
    if existing:
        existing.refresh_token_ciphertext = ciphertext
        existing.user_id = user_id
        existing.status = AmazonConnectionStatus.ACTIVE
        existing.last_authorized_at = now
        existing.updated_at = now
        logger.info(
            "Updated Amazon seller connection selling_partner_id=%s organization_id=%s",
            selling_partner_id,
            organization_id or "(none)",
        )
        return existing

    connection = AmazonSellerAuthorization(
        selling_partner_id=selling_partner_id,
        user_id=user_id,
        organization_id=organization_id,
        refresh_token_ciphertext=ciphertext,
        status=AmazonConnectionStatus.ACTIVE,
        connected_at=now,
        last_authorized_at=now,
    )
    db.add(connection)
    logger.info(
        "Created Amazon seller connection selling_partner_id=%s organization_id=%s",
        selling_partner_id,
        organization_id or "(none)",
    )
    return connection
