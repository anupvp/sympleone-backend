"""Synchronize Sales & Traffic reports and order metrics from Amazon SP-API."""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.catalog_items import fetch_catalog_item_title
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.order_items_api import fetch_order_items
from app.services.amazon.orders_api import (
    created_after_from_start_date,
    created_before_from_end_date,
    fetch_orders,
)
from app.services.amazon.sales_order_metrics import previous_period
from app.services.amazon.sales_traffic_report import (
    parse_sales_and_traffic_by_asin,
    fetch_sales_and_traffic_report,
)
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError
from app.services.product_performance import repository as repo

logger = logging.getLogger(__name__)

_ORDER_ITEMS_PAUSE_SECONDS = 0.15
_MAX_ORDERS_FOR_ITEMS = 400


class ProductPerformanceSyncError(Exception):
    """Product performance data could not be synchronized."""


def _parse_date(value: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return fallback


def _order_purchase_date(order: dict[str, Any]) -> date | None:
    raw = order.get("PurchaseDate")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _float_item_price(item: dict[str, Any]) -> float:
    price = item.get("ItemPrice")
    if not isinstance(price, dict):
        return 0.0
    amount = price.get("Amount")
    try:
        return float(amount) if amount is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def sync_product_performance_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> dict[str, Any]:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise ProductPerformanceSyncError(
            "Product performance sync is only available for seller accounts"
        )

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise ProductPerformanceSyncError(
            "Connect your Amazon seller account before syncing product performance"
        )

    today = datetime.now(UTC).date()
    default_start = today.replace(day=1)
    start = _parse_date(date_from, default_start)
    end = _parse_date(date_to, today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    prev_start, prev_end = previous_period(start, end)

    sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)
    if sync_state.sync_in_progress:
        raise ProductPerformanceSyncError(
            "A product performance sync is already in progress for this seller and marketplace"
        )

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise ProductPerformanceSyncError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    repo.set_sync_in_progress(db, sync_state, in_progress=True)
    db.commit()

    try:
        for period_start, period_end in ((start, end), (prev_start, prev_end)):
            payload = fetch_sales_and_traffic_report(
                access_token=access_token,
                marketplace_id=marketplace,
                start=period_start,
                end=period_end,
            )
            rows = parse_sales_and_traffic_by_asin(payload)
            repo.clear_daily_for_period_end(
                db,
                seller_id=subject.id,
                marketplace_id=marketplace,
                report_date=period_end,
            )
            for row in rows:
                repo.upsert_daily_row(
                    db,
                    seller_id=subject.id,
                    marketplace_id=marketplace,
                    sku=row.sku,
                    asin=row.asin,
                    report_date=period_end,
                    units_ordered=row.units_ordered,
                    ordered_sales=row.ordered_sales,
                    total_order_items=row.total_order_items,
                    units_shipped=row.units_shipped,
                    shipped_sales=row.shipped_sales,
                )

        combined_start = prev_start
        repo.clear_order_metrics_in_range(
            db,
            seller_id=subject.id,
            marketplace_id=marketplace,
            start=combined_start,
            end=end,
        )

        orders = fetch_orders(
            access_token=access_token,
            marketplace_id=marketplace,
            created_after=created_after_from_start_date(combined_start),
            created_before=created_before_from_end_date(end),
        )
        if len(orders) > _MAX_ORDERS_FOR_ITEMS:
            logger.warning(
                "Truncating order-items sync at %s orders (seller=%s)",
                _MAX_ORDERS_FOR_ITEMS,
                subject.id[:8],
            )
            orders = orders[:_MAX_ORDERS_FOR_ITEMS]

        title_cache: dict[str, str] = {}
        asin_by_sku: dict[str, str | None] = {}

        current_rows = repo.load_daily_snapshot(
            db, seller_id=subject.id, marketplace_id=marketplace, report_date=end
        )
        for daily in current_rows:
            asin_by_sku[daily.sku] = daily.asin

        for order in orders:
            if not isinstance(order, dict):
                continue
            order_id = str(order.get("AmazonOrderId") or "").strip()
            if not order_id:
                continue
            status = str(order.get("OrderStatus") or "").strip()
            if status.lower() in {"canceled", "cancelled"}:
                continue
            purchase_day = _order_purchase_date(order)
            if purchase_day is None:
                continue
            if purchase_day < combined_start or purchase_day > end:
                continue

            time.sleep(_ORDER_ITEMS_PAUSE_SECONDS)
            try:
                items = fetch_order_items(
                    access_token=access_token,
                    marketplace_id=marketplace,
                    order_id=order_id,
                )
            except SpApiRequestError:
                logger.warning("Skipping order items for order_id=%s", order_id[:12])
                continue

            for item in items:
                sku = str(item.get("SellerSKU") or "").strip()
                if not sku:
                    continue
                qty_raw = item.get("QuantityOrdered")
                try:
                    quantity = int(qty_raw) if qty_raw is not None else 0
                except (TypeError, ValueError):
                    quantity = 0
                title = item.get("Title")
                product_title = title.strip() if isinstance(title, str) and title.strip() else None
                if product_title:
                    title_cache.setdefault(sku, product_title)

                repo.upsert_order_metric(
                    db,
                    seller_id=subject.id,
                    marketplace_id=marketplace,
                    sku=sku,
                    order_id=order_id,
                    order_date=purchase_day,
                    quantity=quantity,
                    item_price=_float_item_price(item),
                    order_status=status or None,
                    product_title=product_title,
                )

        for sku, asin in asin_by_sku.items():
            if sku in title_cache or not asin:
                continue
            title = fetch_catalog_item_title(
                access_token=access_token,
                marketplace_id=marketplace,
                asin=asin,
            )
            if title:
                title_cache[sku] = title

        repo.mark_synced(db, sync_state)
        db.commit()
    except Exception:
        db.rollback()
        sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)
        repo.set_sync_in_progress(db, sync_state, in_progress=False)
        db.commit()
        raise

    return {
        "success": True,
        "seller_id": subject.id,
        "marketplace_id": marketplace,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "comparison_start_date": prev_start.isoformat(),
        "comparison_end_date": prev_end.isoformat(),
        "last_synced_at": sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None,
    }