"""Active Products stat: BUYABLE listings + low FBA stock subline."""

from __future__ import annotations

from datetime import date

from app.services.amazon.fba_inventory_summaries import (
    count_low_stock_skus,
    fetch_inventory_summaries,
)
from app.services.amazon.listings_items import (
    count_listings_created_between,
    fetch_buyable_listings,
)


def build_active_products_metrics(
    *,
    access_token: str,
    selling_partner_id: str,
    marketplace_id: str,
    start: date,
    end: date,
    prev_start: date,
    prev_end: date,
) -> tuple[int, int, int, int | None]:
    """
    Returns (buyable_total, new_in_current_period, new_in_previous_period, low_stock).
    Listings are point-in-time; period comparison uses new SKUs by createdDate.
    """
    buyable_total, items = fetch_buyable_listings(
        access_token=access_token,
        selling_partner_id=selling_partner_id,
        marketplace_id=marketplace_id,
    )
    new_current = count_listings_created_between(items, start, end)
    new_previous = count_listings_created_between(items, prev_start, prev_end)

    low_stock: int | None = None
    try:
        summaries = fetch_inventory_summaries(
            access_token=access_token,
            marketplace_id=marketplace_id,
            start=start,
        )
        low_stock = count_low_stock_skus(summaries)
    except Exception:
        low_stock = None

    return buyable_total, new_current, new_previous, low_stock