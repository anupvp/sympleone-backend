import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AmazonConnectionStatus(str, enum.Enum):
    """Connection lifecycle for an Amazon seller authorization."""

    ACTIVE = "active"
    REVOKED = "revoked"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AmazonSellerAuthorization(Base):
    """
    Amazon seller connection (OAuth / SP-API).

    Spec name: AmazonConnection. Persists selling_partner_id per organization with an
    encrypted LWA refresh token (`refresh_token_ciphertext`). Access tokens are not stored.
    """

    __tablename__ = "amazon_seller_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "selling_partner_id",
            name="uq_amazon_seller_org_partner",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    selling_partner_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    refresh_token_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[AmazonConnectionStatus] = mapped_column(
        Enum(AmazonConnectionStatus),
        default=AmazonConnectionStatus.ACTIVE,
        index=True,
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
