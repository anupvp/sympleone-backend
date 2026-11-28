from pydantic import BaseModel, Field


class ProductSummaryOut(BaseModel):
    total: int = 0
    active: int = 0
    inactive: int = 0
    out_of_stock: int = 0
    draft: int = 0
    suppressed: int = 0


class ProductListingRowOut(BaseModel):
    sku: str
    asin: str | None = None
    title: str
    category: str
    image_url: str | None = None
    listing_status: str
    fulfillment_type: str
    fulfillment_label: str
    inventory_available: int = 0
    inventory_label: str = "Available"
    price_amount: str | None = None
    price_currency: str = "INR"
    shipping_amount: str | None = None
    estimated_fees_amount: str | None = None
    performance_percent: float | None = None
    updated_at: str | None = None


class ProductsPageOut(BaseModel):
    marketplace_id: str
    summary: ProductSummaryOut
    products: list[ProductListingRowOut] = Field(default_factory=list)