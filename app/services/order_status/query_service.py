"""Read order status aggregates from the local database."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserKind
from app.models.dashboard_orders import NormalizedOrderStatus
from app.services.order_status import repository as repo
from app.services.order_status.percentages import (
    STATUS_COLORS,
    STATUS_LABELS,
    integer_percentages,
)


class OrderStatusQueryError(Exception):
    pass


def _parse_filter_date(value: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return fallback


def _resolve_subject(user: User, seller: User | None) -> User:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise OrderStatusQueryError("Order status is only available for seller accounts")
    return subject


def build_order_status_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> dict:
    subject = _resolve_subject(user, seller)
    today = datetime.now().date()
    default_start = today.replace(day=1)
    start = _parse_filter_date(date_from, default_start)
    end = _parse_filter_date(date_to, today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    counts = repo.count_by_status_in_range(
        db,
        seller_id=subject.id,
        marketplace_id=marketplace,
        start=start,
        end=end,
    )
    total_orders = sum(counts.values())
    pct = integer_percentages(counts, total_orders)

    statuses = []
    for status in (
        NormalizedOrderStatus.DELIVERED,
        NormalizedOrderStatus.IN_TRANSIT,
        NormalizedOrderStatus.PROCESSING,
        NormalizedOrderStatus.CANCELLED,
    ):
        statuses.append(
            {
                "status": status.value,
                "label": STATUS_LABELS[status],
                "count": counts.get(status, 0),
                "percentage": pct[status],
                "color": STATUS_COLORS[status],
            }
        )

    total, delivered_verified, without_tracking = repo.count_coverage_in_range(
        db,
        seller_id=subject.id,
        marketplace_id=marketplace,
        start=start,
        end=end,
    )

    sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)

    return {
        "success": True,
        "data": {
            "total_orders": total_orders,
            "statuses": statuses,
            "currency": "INR",
            "last_synced_at": (
                sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None
            ),
            "data_coverage": {
                "total_orders": total,
                "orders_with_verified_delivery": delivered_verified,
                "orders_without_tracking_information": without_tracking,
            },
            "sync_in_progress": bool(sync_state.sync_in_progress),
            "last_sync_truncated": bool(sync_state.last_sync_truncated),
        },
        "metadata": {
            "seller_id": subject.id,
            "marketplace_id": marketplace,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    }


def get_sync_status_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    seller: User | None = None,
) -> dict:
    subject = _resolve_subject(user, seller)
    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)
    return {
        "success": True,
        "data": {
            "seller_id": subject.id,
            "marketplace_id": marketplace,
            "last_synced_at": (
                sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None
            ),
            "sync_in_progress": bool(sync_state.sync_in_progress),
            "last_sync_truncated": bool(sync_state.last_sync_truncated),
        },
    }