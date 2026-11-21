"""Persisted Amazon orders for dashboard aggregates (order status widget)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NormalizedOrderStatus(str, enum.Enum):
    DELIVERED = "DELIVERED"
    IN_TRANSIT = "IN_TRANSIT"
    PROCESSING = "PROCESSING"
    CANCELLED = "CANCELLED"


class DashboardOrder(Base):
    __tablename__ = "dashboard_orders"
    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace_id",
            "order_id",
            name="uq_dashboard_order",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    marketplace_id: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    purchase_date: Mapped[date] = mapped_column(Date, index=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    fulfillment_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    easy_ship_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    items_shipped: Mapped[int] = mapped_column(Integer, default=0)
    items_unshipped: Mapped[int] = mapped_column(Integer, default=0)
    normalized_status: Mapped[NormalizedOrderStatus] = mapped_column(
        Enum(NormalizedOrderStatus),
        index=True,
    )
    has_tracking_info: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DashboardOrderSyncState(Base):
    __tablename__ = "dashboard_order_sync_state"
    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace_id",
            name="uq_dashboard_order_sync",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    marketplace_id: Mapped[str] = mapped_column(String(32), index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_in_progress: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    last_sync_truncated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )