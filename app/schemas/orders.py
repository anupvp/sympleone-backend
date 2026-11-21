from pydantic import BaseModel, Field


class OrderMoneyOut(BaseModel):
    currency_code: str = ""
    amount: str = ""


class OrderRowOut(BaseModel):
    amazon_order_id: str
    purchase_date: str | None = None
    order_status: str | None = None
    order_total: OrderMoneyOut | None = None
    payment_method: str | None = None
    fulfillment_channel: str | None = None
    fulfillment_type: str = "FBM"
    fulfillment_label: str = "FBM"
    is_prime: bool = False
    sales_channel: str | None = None
    ship_city: str | None = None
    ship_state: str | None = None
    easy_ship_status: str | None = None
    shipment_service_level: str | None = None
    number_of_items_shipped: int = 0
    number_of_items_unshipped: int = 0


class OrdersFulfillmentSummaryOut(BaseModel):
    total: int = 0
    fba: int = 0
    fbm: int = 0
    self_ship: int = 0


class OrdersListOut(BaseModel):
    orders: list[OrderRowOut] = Field(default_factory=list)
    created_after: str | None = None
    created_before: str | None = None
    summary: OrdersFulfillmentSummaryOut = Field(default_factory=OrdersFulfillmentSummaryOut)
