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
    is_prime: bool = False
    sales_channel: str | None = None
    ship_city: str | None = None
    ship_state: str | None = None
    easy_ship_status: str | None = None
    number_of_items_shipped: int = 0
    number_of_items_unshipped: int = 0


class OrdersListOut(BaseModel):
    orders: list[OrderRowOut] = Field(default_factory=list)
    created_before: str | None = None
