"""Products & listings page for seller catalog."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.fba_inventory_summaries import (
    fetch_inventory_summaries_paginated,
)
from app.services.amazon.listings_items import fetch_seller_listings
from app.services.amazon.listings_marketplace_probe import resolve_listings_marketplace_id
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError
from app.services.product_performance import repository as perf_repo
from app.services.product_performance.growth import compute_growth
from app.services.products.listing_mapper import map_listing_item, summarize_listing_rows


class ProductsServiceError(Exception):
    pass


def _fba_qty_by_sku(summaries: list) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in summaries:
        if not isinstance(row, dict):
            continue
        sku = str(row.get("sellerSku") or "").strip()
        if not sku:
            continue
        details = row.get("inventoryDetails")
        qty = 0
        if isinstance(details, dict):
            try:
                qty = int(details.get("fulfillableQuantity") or 0)
            except (TypeError, ValueError):
                qty = 0
        if qty <= 0:
            try:
                qty = int(row.get("totalQuantity") or 0)
            except (TypeError, ValueError):
                qty = 0
        out[sku] = max(out.get(sku, 0), qty)
    return out


def _performance_by_sku(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    period_end: date,
) -> dict[str, float | None]:
    current_rows = {
        r.sku: r
        for r in perf_repo.load_daily_snapshot(
            db,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            report_date=period_end,
        )
    }
    prev_end = period_end.replace(day=1)
    if period_end.month == 1:
        prev_end = date(period_end.year - 1, 12, 1)
    else:
        prev_end = date(period_end.year, period_end.month - 1, 1)

    previous_rows = {
        r.sku: r
        for r in perf_repo.load_daily_snapshot(
            db,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            report_date=prev_end,
        )
    }

    out: dict[str, float | None] = {}
    all_skus = set(current_rows) | set(previous_rows)
    for sku in all_skus:
        current = current_rows.get(sku)
        previous = previous_rows.get(sku)
        cur = float(current.ordered_sales) if current else 0.0
        prev = float(previous.ordered_sales) if previous else 0.0
        out[sku] = compute_growth(cur, prev)
    return out


def list_products_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise ProductsServiceError("Products are only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise ProductsServiceError(
            "Connect your Amazon seller account before viewing products"
        )

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise ProductsServiceError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    try:
        marketplace = resolve_listings_marketplace_id(
            access_token,
            selling_partner_id=connection.selling_partner_id,
            marketplace_id=marketplace_id,
        )
        _, listing_items = fetch_seller_listings(
            access_token=access_token,
            selling_partner_id=connection.selling_partner_id,
            marketplace_id=marketplace,
            buyable_only=False,
        )
        fba_rows, _ = fetch_inventory_summaries_paginated(
            access_token=access_token,
            marketplace_id=marketplace,
            start=None,
        )
    except SpApiRequestError as exc:
        raise ProductsServiceError(str(exc)) from exc

    fba_map = _fba_qty_by_sku(fba_rows)
    perf_map = _performance_by_sku(
        db,
        seller_id=subject.id,
        marketplace_id=marketplace,
        period_end=date.today(),
    )

    products = [
        map_listing_item(
            item,
            marketplace_id=marketplace,
            fba_qty_by_sku=fba_map,
            performance_pct_by_sku=perf_map,
        )
        for item in listing_items
        if str(item.get("sku") or "").strip()
    ]
    products.sort(key=lambda row: (row.get("title") or "").lower())

    summary = summarize_listing_rows(products)

    return {
        "marketplace_id": marketplace,
        "summary": summary,
        "products": products,
    }