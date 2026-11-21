from __future__ import annotations

from pydantic import BaseModel, Field


class ProductPerformanceRowOut(BaseModel):
    product_name: str
    sku: str
    asin: str | None = None
    sales: float
    orders: int
    revenue: float
    growth_percentage: float | None = None
    growth_display: str
    currency: str = "INR"


class ProductPerformanceMetadataOut(BaseModel):
    seller_id: str
    marketplace_id: str
    start_date: str
    end_date: str
    comparison_start_date: str
    comparison_end_date: str
    last_synced_at: str | None = None
    total_products: int = 0
    revenue_definition: str | None = None


class ProductPerformanceListOut(BaseModel):
    success: bool = True
    data: list[ProductPerformanceRowOut]
    metadata: ProductPerformanceMetadataOut


class ProductPerformanceSummaryDataOut(BaseModel):
    total_sales: float
    total_orders: int
    total_revenue: float
    currency: str = "INR"
    top_products: list[ProductPerformanceRowOut]
    low_products: list[ProductPerformanceRowOut]


class ProductPerformanceSummaryOut(BaseModel):
    success: bool = True
    data: ProductPerformanceSummaryDataOut
    metadata: ProductPerformanceMetadataOut


class ProductPerformanceSyncOut(BaseModel):
    success: bool = True
    seller_id: str
    marketplace_id: str
    start_date: str
    end_date: str
    comparison_start_date: str
    comparison_end_date: str
    last_synced_at: str | None = None

    model_config = {"extra": "allow"}