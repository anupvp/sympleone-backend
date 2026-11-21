"""Persisted product performance metrics from Sales & Traffic reports and order lines."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductPerformanceDaily(Base):
    """
    SKU-level metrics for a report period.

    When Amazon only returns period-aggregated ``salesAndTrafficByAsin`` rows, we store
    one row per SKU with ``report_date`` equal to the period end date.
    """

    __tablename__ = "product_performance_daily"
    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace_id",
            "sku",
            "report_date",
            name="uq_product_perf_daily",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    marketplace_id: Mapped[str] = mapped_column(String(32), index=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    asin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    units_ordered: Mapped[int] = mapped_column(Integer, default=0)
    ordered_sales: Mapped[float] = mapped_column(Float, default=0.0)
    total_order_items: Mapped[int] = mapped_column(Integer, default=0)
    units_shipped: Mapped[int] = mapped_column(Integer, default=0)
    shipped_sales: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductOrderMetric(Base):
    """One order line per SKU — used for distinct order counts."""

    __tablename__ = "product_order_metrics"
    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace_id",
            "sku",
            "order_id",
            name="uq_product_order_metric",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    marketplace_id: Mapped[str] = mapped_column(String(32), index=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    order_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    item_price: Mapped[float] = mapped_column(Float, default=0.0)
    order_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductPerformanceSyncState(Base):
    """Tracks last sync and prevents concurrent duplicate processing."""

    __tablename__ = "product_performance_sync_state"
    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace_id",
            name="uq_product_perf_sync",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    marketplace_id: Mapped[str] = mapped_column(String(32), index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_in_progress: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )