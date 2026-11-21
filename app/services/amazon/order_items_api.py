"""Amazon Orders API — order line items for SKU-level order counts."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

_ORDER_ITEMS_PAGE_PAUSE_SECONDS = 0.2
_MAX_ORDER_ITEM_PAGES = 20


def order_items_path(order_id: str) -> str:
    return f"/orders/v0/orders/{quote(order_id, safe='')}/orderItems"


def fetch_order_items(
    *,
    access_token: str,
    marketplace_id: str,
    order_id: str,
) -> list[dict[str, Any]]:
    host = sp_api_host_for_marketplace(marketplace_id)
    path = order_items_path(order_id)
    items: list[dict[str, Any]] = []
    next_token: str | None = None
    pages = 0

    while pages < _MAX_ORDER_ITEM_PAGES:
        query: dict[str, str] | None = {"NextToken": next_token} if next_token else None
        data = sp_api_get(
            host=host,
            path=path,
            query=query,
            access_token=access_token,
        )
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        batch = payload.get("OrderItems") if isinstance(payload.get("OrderItems"), list) else []
        items.extend(i for i in batch if isinstance(i, dict))

        next_token = payload.get("NextToken")
        if not isinstance(next_token, str) or not next_token.strip():
            break
        next_token = next_token.strip()
        pages += 1
        time.sleep(_ORDER_ITEMS_PAGE_PAUSE_SECONDS)

    if pages >= _MAX_ORDER_ITEM_PAGES and next_token:
        logger.warning("Order items pagination truncated for order_id=%s", order_id[:12])

    return items