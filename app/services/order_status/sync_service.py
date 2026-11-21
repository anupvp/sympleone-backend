"""Synchronize Amazon orders into dashboard_orders for status aggregation."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.orders_api import (
    created_after_from_start_date,
    created_before_from_end_date,
    fetch_orders,
)
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError
from app.services.order_status.classifier import classify_amazon_order
from app.services.order_status import repository as repo

logger = logging.getLogger(__name__)

_SYNC_MAX_ORDERS = 2000


class OrderStatusSyncError(Exception):
    pass


def _parse_filter_date(value: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return fallback


def _parse_amazon_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def sync_dashboard_orders_for_user(
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
        raise OrderStatusSyncError("Order status sync is only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise OrderStatusSyncError("Connect your Amazon seller account before syncing orders")

    today = datetime.now(UTC).date()
    default_start = today.replace(day=1)
    start = _parse_filter_date(date_from, default_start)
    end = _parse_filter_date(date_to, today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)
    if sync_state.sync_in_progress:
        raise OrderStatusSyncError(
            "An order status sync is already in progress for this seller and marketplace"
        )

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise OrderStatusSyncError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    repo.set_sync_in_progress(db, sync_state, in_progress=True)
    db.commit()

    truncated = False
    try:
        raw_orders = fetch_orders(
            access_token=access_token,
            marketplace_id=marketplace,
            created_after=created_after_from_start_date(start),
            created_before=created_before_from_end_date(end),
            max_orders=_SYNC_MAX_ORDERS,
        )
        truncated = len(raw_orders) >= _SYNC_MAX_ORDERS

        seen: set[str] = set()
        for raw in raw_orders:
            if not isinstance(raw, dict):
                continue
            order_id = str(raw.get("AmazonOrderId") or "").strip()
            if not order_id or order_id in seen:
                continue
            seen.add(order_id)

            purchase_dt = _parse_amazon_datetime(raw.get("PurchaseDate"))
            if purchase_dt is None:
                continue
            purchase_day = purchase_dt.date()
            if purchase_day < start or purchase_day > end:
                continue

            normalized, has_tracking = classify_amazon_order(raw)
            repo.upsert_dashboard_order(
                db,
                seller_id=subject.id,
                marketplace_id=marketplace,
                order_id=order_id,
                purchase_date=purchase_day,
                last_updated_at=_parse_amazon_datetime(raw.get("LastUpdateDate")),
                fulfillment_status=str(raw.get("OrderStatus") or "") or None,
                fulfillment_channel=str(raw.get("FulfillmentChannel") or "") or None,
                easy_ship_status=(
                    str(raw.get("EasyShipShipmentStatus")).strip()
                    if raw.get("EasyShipShipmentStatus")
                    else None
                ),
                items_shipped=int(raw.get("NumberOfItemsShipped") or 0),
                items_unshipped=int(raw.get("NumberOfItemsUnshipped") or 0),
                normalized_status=normalized,
                has_tracking_info=has_tracking,
            )

        repo.mark_synced(db, sync_state, truncated=truncated)
        db.commit()
    except SpApiRequestError as exc:
        db.rollback()
        sync_state = repo.get_or_create_sync_state(db, seller_id=subject.id, marketplace_id=marketplace)
        repo.set_sync_in_progress(db, sync_state, in_progress=False)
        db.commit()
        raise OrderStatusSyncError(str(exc)) from exc
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
        "last_synced_at": sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None,
        "truncated": truncated,
    }