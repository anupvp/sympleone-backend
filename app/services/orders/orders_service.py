"""List Amazon orders for the Orders UI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.orders_api import fetch_orders
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError
class OrdersServiceError(Exception):
    pass


def _map_order(raw: dict) -> dict:
    total = raw.get("OrderTotal") or {}
    ship = raw.get("ShippingAddress") or {}
    return {
        "amazon_order_id": str(raw.get("AmazonOrderId") or ""),
        "purchase_date": raw.get("PurchaseDate"),
        "order_status": raw.get("OrderStatus"),
        "order_total": {
            "currency_code": str(total.get("CurrencyCode") or ""),
            "amount": str(total.get("Amount") or ""),
        }
        if total
        else None,
        "payment_method": raw.get("PaymentMethod"),
        "fulfillment_channel": raw.get("FulfillmentChannel"),
        "is_prime": bool(raw.get("IsPrime")),
        "sales_channel": raw.get("SalesChannel"),
        "ship_city": ship.get("City"),
        "ship_state": ship.get("StateOrRegion"),
        "easy_ship_status": raw.get("EasyShipShipmentStatus"),
        "number_of_items_shipped": int(raw.get("NumberOfItemsShipped") or 0),
        "number_of_items_unshipped": int(raw.get("NumberOfItemsUnshipped") or 0),
    }


def list_orders_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    created_after: str,
    created_before: str,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise OrdersServiceError("Orders are only available for a connected seller account")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise OrdersServiceError(
            "Connect your Amazon seller account before viewing orders"
        )

    created_after_val = created_after.strip()
    created_before_val = created_before.strip()
    if not created_after_val or not created_before_val:
        raise OrdersServiceError("CreatedAfter and CreatedBefore are required")

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise OrdersServiceError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    try:
        raw_orders = fetch_orders(
            access_token=access_token,
            marketplace_id=marketplace,
            created_after=created_after_val,
            created_before=created_before_val,
        )
    except SpApiRequestError as exc:
        raise OrdersServiceError(str(exc)) from exc

    orders = [_map_order(row) for row in raw_orders if row.get("AmazonOrderId")]
    orders.sort(key=lambda r: r.get("purchase_date") or "", reverse=True)

    return {
        "orders": orders,
        "created_after": created_after_val,
        "created_before": created_before_val,
    }
