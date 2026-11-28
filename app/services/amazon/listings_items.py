"""Listings Items API — search seller catalog (BUYABLE listings)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

from app.services.amazon.sp_api_client import SpApiRequestError, sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

LISTINGS_ITEMS_VERSION = "2021-08-01"
_MAX_LISTING_PAGES = 60


def listings_items_path(selling_partner_id: str) -> str:
    return f"/listings/{LISTINGS_ITEMS_VERSION}/items/{quote(selling_partner_id, safe='')}"


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def _item_created_date(item: dict[str, Any]) -> datetime | None:
    summaries = item.get("summaries")
    if not isinstance(summaries, list):
        return None
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        raw = summary.get("createdDate")
        if isinstance(raw, str):
            return _parse_iso_datetime(raw)
    return None


def _item_is_buyable(item: dict[str, Any]) -> bool:
    summaries = item.get("summaries")
    if not isinstance(summaries, list):
        return False
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        status = summary.get("status")
        if isinstance(status, list) and any(
            str(s).strip().upper() == "BUYABLE" for s in status
        ):
            return True
    return False


def _normalize_listings_body(data: dict[str, Any]) -> tuple[int | None, str | None, list[dict[str, Any]]]:
    """SP-API may return fields at root or under payload."""
    raw_payload = data.get("payload")
    if isinstance(raw_payload, dict):
        payload = raw_payload
    elif isinstance(data, dict) and "items" in data:
        payload = data
    else:
        return None, None, []
    if not isinstance(payload, dict):
        return None, None, []

    total_raw = payload.get("numberOfResults")
    try:
        total = int(total_raw) if total_raw is not None else None
    except (TypeError, ValueError):
        total = None

    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    next_token = pagination.get("nextToken")
    if isinstance(next_token, str):
        next_token = next_token.strip() or None
    else:
        next_token = None

    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return total, next_token, [i for i in items if isinstance(i, dict)]


def probe_seller_listings_access(
    *,
    access_token: str,
    selling_partner_id: str,
    marketplace_id: str,
) -> None:
    """Lightweight Listings Items request to verify marketplace registration."""
    host = sp_api_host_for_marketplace(marketplace_id)
    path = listings_items_path(selling_partner_id)
    query = {
        "marketplaceIds": marketplace_id,
        "includedData": "summaries",
        "pageSize": "1",
    }
    sp_api_get(host=host, path=path, query=query, access_token=access_token)


def fetch_seller_listings(
    *,
    access_token: str,
    selling_partner_id: str,
    marketplace_id: str,
    page_size: int = 20,
    buyable_only: bool = False,
    max_pages: int | None = None,
    included_data: str = "summaries,attributes,fulfillmentAvailability,offers,issues",
) -> tuple[int, list[dict[str, Any]]]:
    """
    Paginate seller catalog listings. Returns total count (from API when available)
    and fetched item rows.
    """
    host = sp_api_host_for_marketplace(marketplace_id)
    path = listings_items_path(selling_partner_id)
    base_query: dict[str, str] = {
        "marketplaceIds": marketplace_id,
        "includedData": included_data,
        "pageSize": str(max(1, min(page_size, 20))),
    }
    if buyable_only:
        base_query["withStatus"] = "BUYABLE"

    collected: list[dict[str, Any]] = []
    total_reported: int | None = None
    next_token: str | None = None
    pages = 0

    page_limit = max_pages if max_pages is not None else _MAX_LISTING_PAGES
    while pages < page_limit:
        query = dict(base_query)
        if next_token:
            query["pageToken"] = next_token

        data = sp_api_get(
            host=host,
            path=path,
            query=query,
            access_token=access_token,
        )
        total, next_token, batch = _normalize_listings_body(data)
        if total_reported is None and total is not None:
            total_reported = total
        for item in batch:
            if buyable_only and not _item_is_buyable(item):
                continue
            collected.append(item)

        pages += 1
        if not next_token:
            break

    if pages >= _MAX_LISTING_PAGES and next_token:
        logger.warning(
            "Listings pagination truncated at %s items for seller %s",
            len(collected),
            selling_partner_id[:8],
        )

    if total_reported is not None and not buyable_only:
        count = len(collected)
    elif total_reported is not None:
        count = total_reported
    else:
        count = len(collected)
    return count, collected


def fetch_buyable_listings(
    *,
    access_token: str,
    selling_partner_id: str,
    marketplace_id: str,
    page_size: int = 20,
) -> tuple[int, list[dict[str, Any]]]:
    return fetch_seller_listings(
        access_token=access_token,
        selling_partner_id=selling_partner_id,
        marketplace_id=marketplace_id,
        page_size=page_size,
        buyable_only=True,
    )


def count_listings_created_between(
    items: list[dict[str, Any]],
    start: date,
    end: date,
) -> int:
    total = 0
    for item in items:
        created = _item_created_date(item)
        if created is None:
            continue
        day = created.date()
        if start <= day <= end:
            total += 1
    return total