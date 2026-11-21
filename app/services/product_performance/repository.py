"""Database access for product performance tables."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.product_performance import (
    ProductOrderMetric,
    ProductPerformanceDaily,
    ProductPerformanceSyncState,
)


def get_or_create_sync_state(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
) -> ProductPerformanceSyncState:
    row = db.execute(
        select(ProductPerformanceSyncState).where(
            ProductPerformanceSyncState.seller_id == seller_id,
            ProductPerformanceSyncState.marketplace_id == marketplace_id,
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = ProductPerformanceSyncState(seller_id=seller_id, marketplace_id=marketplace_id)
    db.add(row)
    db.flush()
    return row


def set_sync_in_progress(db: Session, state: ProductPerformanceSyncState, *, in_progress: bool) -> None:
    state.sync_in_progress = in_progress
    state.updated_at = datetime.now(UTC)
    db.add(state)


def mark_synced(db: Session, state: ProductPerformanceSyncState) -> None:
    now = datetime.now(UTC)
    state.last_synced_at = now
    state.sync_in_progress = False
    state.updated_at = now
    db.add(state)


def upsert_daily_row(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    sku: str,
    asin: str | None,
    report_date: date,
    units_ordered: int,
    ordered_sales: float,
    total_order_items: int,
    units_shipped: int,
    shipped_sales: float,
) -> None:
    existing = db.execute(
        select(ProductPerformanceDaily).where(
            ProductPerformanceDaily.seller_id == seller_id,
            ProductPerformanceDaily.marketplace_id == marketplace_id,
            ProductPerformanceDaily.sku == sku,
            ProductPerformanceDaily.report_date == report_date,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            ProductPerformanceDaily(
                seller_id=seller_id,
                marketplace_id=marketplace_id,
                sku=sku,
                asin=asin,
                report_date=report_date,
                units_ordered=units_ordered,
                ordered_sales=ordered_sales,
                total_order_items=total_order_items,
                units_shipped=units_shipped,
                shipped_sales=shipped_sales,
            )
        )
        return

    existing.asin = asin or existing.asin
    existing.units_ordered = units_ordered
    existing.ordered_sales = ordered_sales
    existing.total_order_items = total_order_items
    existing.units_shipped = units_shipped
    existing.shipped_sales = shipped_sales
    db.add(existing)


def clear_daily_for_period_end(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    report_date: date,
) -> None:
    db.execute(
        delete(ProductPerformanceDaily).where(
            ProductPerformanceDaily.seller_id == seller_id,
            ProductPerformanceDaily.marketplace_id == marketplace_id,
            ProductPerformanceDaily.report_date == report_date,
        )
    )


def upsert_order_metric(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    sku: str,
    order_id: str,
    order_date: date,
    quantity: int,
    item_price: float,
    order_status: str | None,
    product_title: str | None,
) -> None:
    existing = db.execute(
        select(ProductOrderMetric).where(
            ProductOrderMetric.seller_id == seller_id,
            ProductOrderMetric.marketplace_id == marketplace_id,
            ProductOrderMetric.sku == sku,
            ProductOrderMetric.order_id == order_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            ProductOrderMetric(
                seller_id=seller_id,
                marketplace_id=marketplace_id,
                sku=sku,
                order_id=order_id,
                order_date=order_date,
                quantity=quantity,
                item_price=item_price,
                order_status=order_status,
                product_title=product_title,
            )
        )
        return

    existing.order_date = order_date
    existing.quantity = quantity
    existing.item_price = item_price
    existing.order_status = order_status
    if product_title:
        existing.product_title = product_title
    db.add(existing)


def clear_order_metrics_in_range(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> None:
    db.execute(
        delete(ProductOrderMetric).where(
            ProductOrderMetric.seller_id == seller_id,
            ProductOrderMetric.marketplace_id == marketplace_id,
            ProductOrderMetric.order_date >= start,
            ProductOrderMetric.order_date <= end,
        )
    )


def load_daily_snapshot(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    report_date: date,
) -> list[ProductPerformanceDaily]:
    return list(
        db.execute(
            select(ProductPerformanceDaily).where(
                ProductPerformanceDaily.seller_id == seller_id,
                ProductPerformanceDaily.marketplace_id == marketplace_id,
                ProductPerformanceDaily.report_date == report_date,
            )
        ).scalars()
    )


def distinct_order_count_by_sku(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> dict[str, int]:
    rows = db.execute(
        select(
            ProductOrderMetric.sku,
            func.count(func.distinct(ProductOrderMetric.order_id)),
        )
        .where(
            ProductOrderMetric.seller_id == seller_id,
            ProductOrderMetric.marketplace_id == marketplace_id,
            ProductOrderMetric.order_date >= start,
            ProductOrderMetric.order_date <= end,
            or_(
                ProductOrderMetric.order_status.is_(None),
                ProductOrderMetric.order_status.notin_(
                    ["Canceled", "Cancelled", "canceled", "cancelled"]
                ),
            ),
        )
        .group_by(ProductOrderMetric.sku)
    ).all()
    return {str(sku): int(count) for sku, count in rows}


def product_titles_by_sku(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
) -> dict[str, str]:
    rows = db.execute(
        select(ProductOrderMetric.sku, ProductOrderMetric.product_title)
        .where(
            ProductOrderMetric.seller_id == seller_id,
            ProductOrderMetric.marketplace_id == marketplace_id,
            ProductOrderMetric.product_title.isnot(None),
        )
        .distinct()
    ).all()
    titles: dict[str, str] = {}
    for sku, title in rows:
        if title and str(title).strip():
            titles[str(sku)] = str(title).strip()
    return titles