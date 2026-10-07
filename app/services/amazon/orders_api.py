"""Amazon Orders API (getOrders)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

ORDERS_PATH = "/orders/v0/orders"


def created_after_from_start_date(d: date) -> str:
    """Matches SP-API Postman pattern: start date at 23:59:59Z."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def created_before_from_end_date(end: date) -> str:
    """Exclusive upper bound: 00:00:00Z on the day after `end`."""
    next_day = end + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def fetch_orders(
    *,
    access_token: str,
    marketplace_id: str,
    created_after: str,
    created_before: str,
) -> list[dict[str, Any]]:
    host = sp_api_host_for_marketplace(marketplace_id)
    query: dict[str, str] = {
        "MarketplaceIds": marketplace_id,
        "CreatedAfter": created_after,
        "CreatedBefore": created_before,
    }

    orders: list[dict[str, Any]] = []
    next_token: str | None = None

    while True:
        page_query = dict(query)
        if next_token:
            page_query["NextToken"] = next_token

        data = sp_api_get(
            host=host,
            path=ORDERS_PATH,
            query=page_query,
            access_token=access_token,
        )
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        batch = payload.get("Orders") if isinstance(payload.get("Orders"), list) else []
        orders.extend(batch)

        next_token = payload.get("NextToken")
        if not next_token:
            break
        if len(orders) > 500:
            logger.warning("Orders pagination truncated at %s rows", len(orders))
            break

    return orders
