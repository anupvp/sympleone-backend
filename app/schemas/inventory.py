from pydantic import BaseModel, Field


class FbaInventoryMetricsOut(BaseModel):
    fulfillable: int = 0
    reserved: int = 0
    inbound: int = 0
    unfulfillable: int = 0


class FbaInventoryItemOut(BaseModel):
    asin: str | None = None
    sellerSku: str | None = None
    fnSku: str | None = None
    productName: str | None = None
    condition: str | None = None
    fulfillable: int = 0
    reserved: int = 0
    inbound: int = 0
    unfulfillable: int = 0
    totalQuantity: int = 0
    lastUpdatedTime: str | None = None


class FbaInventoryOut(BaseModel):
    marketplaceId: str
    granularityType: str | None = None
    truncated: bool = False
    isEmpty: bool = True
    metrics: FbaInventoryMetricsOut
    items: list[FbaInventoryItemOut] = Field(default_factory=list)