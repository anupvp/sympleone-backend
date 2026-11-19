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
_MAX_INVENTORY_PAGES = 40


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _reserved_quantity(details: dict[str, Any]) -> int:
    raw = details.get("reservedQuantity")
    if isinstance(raw, dict):
        return _safe_int(raw.get("totalReservedQuantity"))
    return _safe_int(raw)


def _unfulfillable_quantity(details: dict[str, Any]) -> int:
    raw = details.get("unfulfillableQuantity")
    if isinstance(raw, dict):
        return _safe_int(raw.get("totalUnfulfillableQuantity"))
    return _safe_int(raw)


def _inbound_quantity(details: dict[str, Any]) -> int:
    return (
        _safe_int(details.get("inboundWorkingQuantity"))
        + _safe_int(details.get("inboundShippedQuantity"))
        + _safe_int(details.get("inboundReceivingQuantity"))
    )


def summarize_inventory_metrics(
    summaries: list[dict[str, Any]],
) -> dict[str, int]:
    fulfillable = 0
    reserved = 0
    inbound = 0
    unfulfillable = 0
    for row in summaries:
        if not isinstance(row, dict):
            continue
        details = row.get("inventoryDetails")
        if not isinstance(details, dict):
            details = {}
        fulfillable += _safe_int(details.get("fulfillableQuantity"))
        reserved += _reserved_quantity(details)
        inbound += _inbound_quantity(details)
        unfulfillable += _unfulfillable_quantity(details)
    return {
        "fulfillable": fulfillable,
        "reserved": reserved,
        "inbound": inbound,
        "unfulfillable": unfulfillable,
    }


def normalize_inventory_item(row: dict[str, Any]) -> dict[str, object]:
    details = row.get("inventoryDetails")
    if not isinstance(details, dict):
        details = {}
    fulfillable = _safe_int(details.get("fulfillableQuantity"))
    if fulfillable == 0:
        fulfillable = _safe_int(row.get("totalQuantity"))
    return {
        "asin": str(row.get("asin") or "") or None,
        "sellerSku": str(row.get("sellerSku") or "") or None,
        "fnSku": str(row.get("fnSku") or "") or None,
        "productName": str(row.get("productName") or "") or None,
        "condition": str(row.get("condition") or "") or None,
        "fulfillable": fulfillable,
        "reserved": _reserved_quantity(details),
        "inbound": _inbound_quantity(details),
        "unfulfillable": _unfulfillable_quantity(details),
        "totalQuantity": _safe_int(row.get("totalQuantity")),
        "lastUpdatedTime": (
            str(row.get("lastUpdatedTime")) if row.get("lastUpdatedTime") else None
        ),
    }


def fetch_inventory_summaries_paginated(
    *,
    access_token: str,
    marketplace_id: str,
    start: date | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    host = sp_api_host_for_marketplace(marketplace_id)
    query: dict[str, str] = {
        "marketplaceIds": marketplace_id,
        "granularityId": marketplace_id,
        "granularityType": "Marketplace",
        "details": "true",
    }
    if start is not None:
        query["startDateTime"] = posted_after_from_start_date(start)

    rows: list[dict[str, Any]] = []
    next_token: str | None = None
    pages = 0

    while pages < _MAX_INVENTORY_PAGES:
        page_query = dict(query)
        if next_token:
            page_query["nextToken"] = next_token

        data = sp_api_get(
            host=host,
            path=INVENTORY_SUMMARIES_PATH,
            query=page_query,
            access_token=access_token,
        )
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        batch = payload.get("inventorySummaries")
        if isinstance(batch, list):
            for item in batch:
                if isinstance(item, dict):
                    rows.append(item)

        pagination = payload.get("pagination")
        next_token = None
        if isinstance(pagination, dict):
            raw = pagination.get("nextToken")
            if isinstance(raw, str) and raw.strip():
                next_token = raw.strip()

        pages += 1
        if not next_token:
            break

    truncated = bool(pages >= _MAX_INVENTORY_PAGES and next_token)
    if truncated:
        logger.warning(
            "FBA inventory pagination truncated at %s rows for marketplace %s",
            len(rows),
            marketplace_id,
        )
    return rows, truncated


def fetch_inventory_summaries(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
) -> list[dict[str, Any]]:
    rows, _ = fetch_inventory_summaries_paginated(
        access_token=access_token,
        marketplace_id=marketplace_id,
        start=start,
    )
    return rows


LOW_STOCK_QUANTITY_THRESHOLD = 5


def count_low_stock_skus(
    summaries: list[dict[str, Any]],
    *,
    threshold: int = LOW_STOCK_QUANTITY_THRESHOLD,
) -> int:
    low = 0
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
        if 0 < qty <= threshold:
            low += 1
        elif qty == 0:
            low += 1
    return low


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
