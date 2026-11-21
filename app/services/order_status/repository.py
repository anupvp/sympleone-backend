"""Database access for dashboard order status."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.dashboard_orders import (
    DashboardOrder,
    DashboardOrderSyncState,
    NormalizedOrderStatus,
)


def get_or_create_sync_state(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
) -> DashboardOrderSyncState:
    row = db.execute(
        select(DashboardOrderSyncState).where(
            DashboardOrderSyncState.seller_id == seller_id,
            DashboardOrderSyncState.marketplace_id == marketplace_id,
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = DashboardOrderSyncState(seller_id=seller_id, marketplace_id=marketplace_id)
    db.add(row)
    db.flush()
    return row


def set_sync_in_progress(db: Session, state: DashboardOrderSyncState, *, in_progress: bool) -> None:
    state.sync_in_progress = in_progress
    state.updated_at = datetime.now(UTC)
    db.add(state)


def mark_synced(
    db: Session,
    state: DashboardOrderSyncState,
    *,
    truncated: bool,
) -> None:
    now = datetime.now(UTC)
    state.last_synced_at = now
    state.sync_in_progress = False
    state.last_sync_truncated = truncated
    state.updated_at = now
    db.add(state)


def upsert_dashboard_order(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    order_id: str,
    purchase_date: date,
    last_updated_at: datetime | None,
    fulfillment_status: str | None,
    fulfillment_channel: str | None,
    easy_ship_status: str | None,
    items_shipped: int,
    items_unshipped: int,
    normalized_status: NormalizedOrderStatus,
    has_tracking_info: bool,
) -> None:
    existing = db.execute(
        select(DashboardOrder).where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            DashboardOrder.order_id == order_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            DashboardOrder(
                seller_id=seller_id,
                marketplace_id=marketplace_id,
                order_id=order_id,
                purchase_date=purchase_date,
                last_updated_at=last_updated_at,
                fulfillment_status=fulfillment_status,
                fulfillment_channel=fulfillment_channel,
                easy_ship_status=easy_ship_status,
                items_shipped=items_shipped,
                items_unshipped=items_unshipped,
                normalized_status=normalized_status,
                has_tracking_info=has_tracking_info,
            )
        )
        return

    existing.purchase_date = purchase_date
    existing.last_updated_at = last_updated_at
    existing.fulfillment_status = fulfillment_status
    existing.fulfillment_channel = fulfillment_channel
    existing.easy_ship_status = easy_ship_status
    existing.items_shipped = items_shipped
    existing.items_unshipped = items_unshipped
    existing.normalized_status = normalized_status
    existing.has_tracking_info = has_tracking_info
    db.add(existing)


def remove_orders_outside_range(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> None:
    db.execute(
        delete(DashboardOrder).where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            (
                (DashboardOrder.purchase_date < start)
                | (DashboardOrder.purchase_date > end)
            ),
        )
    )


def count_by_status_in_range(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> dict[NormalizedOrderStatus, int]:
    rows = db.execute(
        select(DashboardOrder.normalized_status, func.count())
        .where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            DashboardOrder.purchase_date >= start,
            DashboardOrder.purchase_date <= end,
        )
        .group_by(DashboardOrder.normalized_status)
    ).all()
    counts = {status: 0 for status in NormalizedOrderStatus}
    for status, count in rows:
        counts[status] = int(count)
    return counts


def count_coverage_in_range(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> tuple[int, int, int]:
    total = db.execute(
        select(func.count())
        .select_from(DashboardOrder)
        .where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            DashboardOrder.purchase_date >= start,
            DashboardOrder.purchase_date <= end,
        )
    ).scalar_one()
    delivered = db.execute(
        select(func.count())
        .select_from(DashboardOrder)
        .where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            DashboardOrder.purchase_date >= start,
            DashboardOrder.purchase_date <= end,
            DashboardOrder.normalized_status == NormalizedOrderStatus.DELIVERED,
        )
    ).scalar_one()
    without_tracking = db.execute(
        select(func.count())
        .select_from(DashboardOrder)
        .where(
            DashboardOrder.seller_id == seller_id,
            DashboardOrder.marketplace_id == marketplace_id,
            DashboardOrder.purchase_date >= start,
            DashboardOrder.purchase_date <= end,
            DashboardOrder.has_tracking_info.is_(False),
        )
    ).scalar_one()
    return int(total), int(delivered), int(without_tracking)