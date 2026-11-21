"""Catalog Items API — resolve product titles by ASIN."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

CATALOG_VERSION = "2022-04-01"


def _catalog_item_path(asin: str) -> str:
    return f"/catalog/{CATALOG_VERSION}/items/{quote(asin, safe='')}"


def _title_from_catalog_payload(data: dict[str, Any]) -> str | None:
    summaries = data.get("summaries")
    if isinstance(summaries, list):
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            title = summary.get("itemName") or summary.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()

    attributes = data.get("attributes")
    if isinstance(attributes, dict):
        item_name = attributes.get("item_name")
        if isinstance(item_name, list) and item_name:
            first = item_name[0]
            if isinstance(first, dict):
                value = first.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def fetch_catalog_item_title(
    *,
    access_token: str,
    marketplace_id: str,
    asin: str,
) -> str | None:
    asin_clean = asin.strip()
    if not asin_clean:
        return None
    host = sp_api_host_for_marketplace(marketplace_id)
    try:
        data = sp_api_get(
            host=host,
            path=_catalog_item_path(asin_clean),
            query={
                "marketplaceIds": marketplace_id,
                "includedData": "summaries,attributes",
            },
            access_token=access_token,
        )
    except Exception:
        logger.debug("Catalog lookup failed for asin=%s", asin_clean[:10])
        return None

    root = data if isinstance(data, dict) else {}
    payload = root.get("payload") if isinstance(root.get("payload"), dict) else root
    if not isinstance(payload, dict):
        return None
    return _title_from_catalog_payload(payload)