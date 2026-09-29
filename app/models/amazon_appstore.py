import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AmazonAppstoreOAuthSession(Base):
    """Short-lived session for Selling Partner Appstore login → Amazon callback redirect."""

    __tablename__ = "amazon_appstore_oauth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    internal_state: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amazon_state: Mapped[str] = mapped_column(String(512), index=True)
    selling_partner_id: Mapped[str] = mapped_column(String(64), index=True)
    amazon_callback_uri: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
