from __future__ import annotations

from pydantic import BaseModel, Field


class OrderStatusSegmentOut(BaseModel):
    status: str
    label: str
    count: int
    percentage: int
    color: str


class OrderStatusDataCoverageOut(BaseModel):
    total_orders: int
    orders_with_verified_delivery: int
    orders_without_tracking_information: int


class OrderStatusDataOut(BaseModel):
    total_orders: int
    statuses: list[OrderStatusSegmentOut]
    currency: str = "INR"
    last_synced_at: str | None = None
    data_coverage: OrderStatusDataCoverageOut
    sync_in_progress: bool = False
    last_sync_truncated: bool = False


class OrderStatusMetadataOut(BaseModel):
    seller_id: str
    marketplace_id: str
    start_date: str
    end_date: str


class OrderStatusOut(BaseModel):
    success: bool = True
    data: OrderStatusDataOut
    metadata: OrderStatusMetadataOut


class OrderStatusSyncOut(BaseModel):
    success: bool = True
    seller_id: str
    marketplace_id: str
    start_date: str
    end_date: str
    last_synced_at: str | None = None
    truncated: bool = False


class OrderStatusSyncStatusDataOut(BaseModel):
    seller_id: str
    marketplace_id: str
    last_synced_at: str | None = None
    sync_in_progress: bool = False
    last_sync_truncated: bool = False


class OrderStatusSyncStatusOut(BaseModel):
    success: bool = True
    data: OrderStatusSyncStatusDataOut