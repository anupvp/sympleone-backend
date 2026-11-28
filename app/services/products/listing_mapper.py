"""Map Amazon Listings Items payloads to Products UI rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _summary_for_marketplace(item: dict[str, Any], marketplace_id: str) -> dict[str, Any]:
    summaries = item.get("summaries")
    if not isinstance(summaries, list):
        return {}
    for summary in summaries:
        if isinstance(summary, dict) and summary.get("marketplaceId") == marketplace_id:
            return summary
    for summary in summaries:
        if isinstance(summary, dict):
            return summary
    return {}


def _status_set(summary: dict[str, Any]) -> set[str]:
    raw = summary.get("status")
    if not isinstance(raw, list):
        return set()
    return {str(s).strip().upper() for s in raw if str(s).strip()}


def _attr_scalar(attributes: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(attributes, dict):
        return None
    raw = attributes.get(key)
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            value = first.get("value")
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _offer_price(item: dict[str, Any]) -> tuple[str | None, str | None]:
    offers = item.get("offers")
    if not isinstance(offers, list):
        return None, None
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        price = offer.get("price")
        if isinstance(price, dict):
            amount = price.get("amount")
            currency = price.get("currency")
            if amount is not None:
                return str(amount), str(currency or "").strip() or None
    return None, None


def _fulfillment_type(item: dict[str, Any], marketplace_id: str, has_fba_stock: bool) -> str:
    fulfill = item.get("fulfillmentAvailability")
    if isinstance(fulfill, list):
        for row in fulfill:
            if not isinstance(row, dict):
                continue
            channel = str(row.get("fulfillmentChannelCode") or "").upper()
            if channel == "AMAZON":
                return "FBA"
    if has_fba_stock:
        return "FBA"
    return "FBM"


def _inventory_available(item: dict[str, Any], marketplace_id: str, fba_qty: int) -> int:
    fulfill = item.get("fulfillmentAvailability")
    if isinstance(fulfill, list):
        for row in fulfill:
            if not isinstance(row, dict):
                continue
            if row.get("marketplaceId") not in (None, marketplace_id):
                continue
            qty = row.get("quantity")
            try:
                parsed = int(qty) if qty is not None else None
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None:
                return max(parsed, 0)
    return fba_qty


def classify_listing_bucket(
    status_set: set[str],
    *,
    has_issues: bool,
    inventory: int,
) -> str:
    if has_issues:
        return "suppressed"
    if status_set & {"INCOMPLETE", "DRAFT"}:
        return "draft"
    if "BUYABLE" in status_set:
        if inventory <= 0:
            return "out_of_stock"
        return "active"
    if "DISCOVERABLE" in status_set:
        return "inactive"
    if status_set & {"SUPPRESSED", "RETIRED", "DELETED"}:
        return "suppressed"
    return "inactive"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def map_listing_item(
    item: dict[str, Any],
    *,
    marketplace_id: str,
    fba_qty_by_sku: dict[str, int],
    performance_pct_by_sku: dict[str, float | None],
) -> dict[str, Any]:
    sku = str(item.get("sku") or "").strip()
    summary = _summary_for_marketplace(item, marketplace_id)
    status_set = _status_set(summary)
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}

    title = summary.get("itemName") or _attr_scalar(attributes, "item_name") or sku or "—"
    asin = summary.get("asin")
    product_type = summary.get("productType") or _attr_scalar(attributes, "product_type")
    category = str(product_type or "General").replace("_", " ").title()

    image = None
    main_image = summary.get("mainImage")
    if isinstance(main_image, dict):
        link = main_image.get("link")
        if isinstance(link, str) and link.strip():
            image = link.strip()

    fba_qty = fba_qty_by_sku.get(sku, 0)
    fulfillment_type = _fulfillment_type(item, marketplace_id, fba_qty > 0)
    inventory = _inventory_available(item, marketplace_id, fba_qty)

    issues = item.get("issues")
    has_issues = isinstance(issues, list) and len(issues) > 0
    listing_status = classify_listing_bucket(status_set, has_issues=has_issues, inventory=inventory)

    price_amount, price_currency = _offer_price(item)
    if not price_amount:
        price_amount = _attr_scalar(attributes, "list_price")

    shipping_amount = _attr_scalar(attributes, "merchant_shipping_group")
    performance = performance_pct_by_sku.get(sku)

    updated = _parse_iso_datetime(summary.get("lastUpdatedDate") or summary.get("createdDate"))

    est_fees: str | None = None
    if price_amount:
        try:
            est_fees = f"{float(price_amount) * 0.15:.2f}"
        except (TypeError, ValueError):
            est_fees = None

    return {
        "sku": sku,
        "asin": asin,
        "title": title,
        "category": category,
        "image_url": image,
        "listing_status": listing_status,
        "fulfillment_type": fulfillment_type,
        "fulfillment_label": "Amazon FBA" if fulfillment_type == "FBA" else "Merchant FBM",
        "inventory_available": inventory,
        "inventory_label": "Available" if inventory > 0 else "Restock",
        "price_amount": price_amount,
        "price_currency": price_currency or "INR",
        "shipping_amount": shipping_amount,
        "estimated_fees_amount": est_fees,
        "performance_percent": performance,
        "updated_at": updated.isoformat() if updated else None,
    }


def summarize_listing_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(rows),
        "active": 0,
        "inactive": 0,
        "out_of_stock": 0,
        "draft": 0,
        "suppressed": 0,
    }
    for row in rows:
        key = row.get("listing_status")
        if key in summary:
            summary[key] += 1
    return summary