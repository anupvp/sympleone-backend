"""Map Amazon Orders API (v0) payloads to dashboard status buckets."""

from __future__ import annotations

import logging
from typing import Any

from app.models.dashboard_orders import NormalizedOrderStatus

logger = logging.getLogger(__name__)

_PROCESSING_ORDER_STATUSES = {
    "PENDING",
    "UNSHIPPED",
    "PARTIALLY_SHIPPED",
    "PENDING_AVAILABILITY",
    "INVOICE_UNCONFIRMED",
    "UNFULFILLABLE",
}

_CANCELLED_ORDER_STATUSES = {"CANCELED", "CANCELLED"}

_EASYSHIP_DELIVERED = {
    "DELIVERED",
    "DROPPEDOFF",
    "DROPPED_OFF",
}

_EASYSHIP_IN_TRANSIT = {
    "PICKEDUP",
    "PICKED_UP",
    "OUTFORDELIVERY",
    "OUT_FOR_DELIVERY",
    "ATDESTINATIONFC",
    "AT_DESTINATION_FC",
    "ATORIGINFC",
    "AT_ORIGIN_FC",
    "PENDINGPICKUP",
    "PENDING_PICKUP",
    "PENDINGDROPOFF",
    "PENDING_DROPOFF",
    "RETURNINGTOSELLER",
    "RETURNING_TO_SELLER",
    "RETURNEDTOSELLER",
    "RETURNED_TO_SELLER",
}


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def _compact(value: str) -> str:
    return _normalize_token(value).replace("_", "")


def _easy_ship_bucket(status: str | None) -> str | None:
    if not status:
        return None
    compact = _compact(status)
    delivered_keys = {_compact(s) for s in _EASYSHIP_DELIVERED}
    transit_keys = {_compact(s) for s in _EASYSHIP_IN_TRANSIT}
    if compact in delivered_keys:
        return NormalizedOrderStatus.DELIVERED.value
    if compact in transit_keys:
        return NormalizedOrderStatus.IN_TRANSIT.value
    return None


def classify_amazon_order(raw: dict[str, Any]) -> tuple[NormalizedOrderStatus, bool]:
    """
    Classify one order from getOrders / getOrder (v0) fields.

    Returns (normalized_status, has_tracking_info).
    Shipped is never treated as Delivered without explicit delivery signals.
    """
    order_status = _normalize_token(raw.get("OrderStatus"))
    easy_raw = raw.get("EasyShipShipmentStatus")
    easy_ship = str(easy_raw).strip() if isinstance(easy_raw, str) and easy_raw.strip() else None
    has_tracking = bool(easy_ship)

    if order_status in _CANCELLED_ORDER_STATUSES:
        return NormalizedOrderStatus.CANCELLED, has_tracking

    if order_status in _PROCESSING_ORDER_STATUSES:
        return NormalizedOrderStatus.PROCESSING, has_tracking

    easy_bucket = _easy_ship_bucket(easy_ship)
    if easy_bucket == NormalizedOrderStatus.DELIVERED.value:
        return NormalizedOrderStatus.DELIVERED, has_tracking

    try:
        unshipped = int(raw.get("NumberOfItemsUnshipped") or 0)
    except (TypeError, ValueError):
        unshipped = 0

    if order_status == "PARTIALLY_SHIPPED" or (order_status == "SHIPPED" and unshipped > 0):
        return NormalizedOrderStatus.PROCESSING, has_tracking

    if order_status == "SHIPPED":
        if easy_bucket == NormalizedOrderStatus.IN_TRANSIT.value:
            return NormalizedOrderStatus.IN_TRANSIT, has_tracking
        if easy_bucket == NormalizedOrderStatus.DELIVERED.value:
            return NormalizedOrderStatus.DELIVERED, has_tracking
        return NormalizedOrderStatus.IN_TRANSIT, has_tracking

    if order_status:
        logger.info("Unmapped Amazon OrderStatus=%s; defaulting to PROCESSING", order_status)
    return NormalizedOrderStatus.PROCESSING, has_tracking