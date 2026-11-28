"""List Amazon orders for the Orders UI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.marketplace_resolver import normalize_marketplace_for_seller
from app.services.amazon.order_items_api import fetch_order_items
from app.services.amazon.orders_api import fetch_order, fetch_orders
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError
from app.services.orders.fulfillment_type import (
    classify_fulfillment_type,
    fulfillment_label,
    summarize_fulfillment_types,
)


class OrdersServiceError(Exception):
    pass


def _map_order_item(raw: dict) -> dict:
    price = raw.get("ItemPrice") or {}
    return {
        "order_item_id": str(raw.get("OrderItemId") or ""),
        "asin": raw.get("ASIN"),
        "seller_sku": raw.get("SellerSKU"),
        "title": raw.get("Title"),
        "quantity_ordered": int(raw.get("QuantityOrdered") or 0),
        "quantity_shipped": int(raw.get("QuantityShipped") or 0),
        "item_price": {
            "currency_code": str(price.get("CurrencyCode") or ""),
            "amount": str(price.get("Amount") or ""),
        }
        if price
        else None,
    }


def _map_order(raw: dict) -> dict:
    total = raw.get("OrderTotal") or {}
    ship = raw.get("ShippingAddress") or {}
    ftype = classify_fulfillment_type(raw)
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
        "fulfillment_type": ftype,
        "fulfillment_label": fulfillment_label(ftype),
        "is_prime": bool(raw.get("IsPrime")),
        "sales_channel": raw.get("SalesChannel"),
        "ship_city": ship.get("City"),
        "ship_state": ship.get("StateOrRegion"),
        "easy_ship_status": raw.get("EasyShipShipmentStatus"),
        "number_of_items_shipped": int(raw.get("NumberOfItemsShipped") or 0),
        "number_of_items_unshipped": int(raw.get("NumberOfItemsUnshipped") or 0),
        "shipment_service_level": raw.get("ShipmentServiceLevelCategory"),
        "buyer_name": ship.get("Name"),
        "ship_address_line1": ship.get("AddressLine1"),
        "ship_address_line2": ship.get("AddressLine2"),
        "ship_postal_code": ship.get("PostalCode"),
        "ship_country": ship.get("CountryCode"),
        "last_update_date": raw.get("LastUpdateDate"),
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

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise OrdersServiceError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    marketplace = normalize_marketplace_for_seller(access_token, marketplace_id)

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
        "summary": summarize_fulfillment_types(orders),
    }


def get_order_detail_for_user(
    db: Session,
    user: User,
    *,
    amazon_order_id: str,
    marketplace_id: str | None,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise OrdersServiceError("Orders are only available for a connected seller account")

    order_id = amazon_order_id.strip()
    if not order_id:
        raise OrdersServiceError("Order ID is required")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise OrdersServiceError(
            "Connect your Amazon seller account before viewing orders"
        )

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise OrdersServiceError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    marketplace = normalize_marketplace_for_seller(access_token, marketplace_id)

    try:
        raw = fetch_order(
            access_token=access_token,
            marketplace_id=marketplace,
            order_id=order_id,
        )
        if raw is None:
            raise OrdersServiceError("Order not found")
        raw_items = fetch_order_items(
            access_token=access_token,
            marketplace_id=marketplace,
            order_id=order_id,
        )
    except SpApiRequestError as exc:
        raise OrdersServiceError(str(exc)) from exc

    mapped = _map_order(raw)
    mapped["items"] = [_map_order_item(item) for item in raw_items]
    return mapped
