"""FBA Inventory API — active SKU counts (dashboard net profit context)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.services.amazon.finance_transactions import posted_after_from_start_date
from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

INVENTORY_SUMMARIES_PATH = "/fba/inventory/v1/summaries"


def fetch_inventory_summaries(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
) -> list[dict[str, Any]]:
    host = sp_api_host_for_marketplace(marketplace_id)
    query = {
        "marketplaceIds": marketplace_id,
        "granularityId": marketplace_id,
        "granularityType": "Marketplace",
        "details": "true",
        "startDateTime": posted_after_from_start_date(start),
    }
    data = sp_api_get(
        host=host,
        path=INVENTORY_SUMMARIES_PATH,
        query=query,
        access_token=access_token,
    )
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    summaries = payload.get("inventorySummaries")
    if not isinstance(summaries, list):
        return []
    return [s for s in summaries if isinstance(s, dict)]


def count_fulfillable_skus(summaries: list[dict[str, Any]]) -> int:
    count = 0
    for row in summaries:
        details = row.get("inventoryDetails") or {}
        if not isinstance(details, dict):
            details = {}
        fulfillable = details.get("fulfillableQuantity")
        if fulfillable is None:
            fulfillable = row.get("totalQuantity")
        try:
            qty = int(fulfillable or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty > 0:
            count += 1
    return count
