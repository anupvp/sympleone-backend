"""Build dashboard sales trend from Amazon order metrics."""

from __future__ import annotations

import logging
from datetime import date, datetime

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
from app.services.amazon.sales_order_metrics import fetch_order_metrics, previous_period
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError


logger = logging.getLogger(__name__)


class SalesTrendError(Exception):
    """Sales trend could not be produced for the dashboard."""


_CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


def _parse_filter_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return fallback


def _format_point_label(iso_day: str) -> str:
    try:
        d = date.fromisoformat(iso_day)
        return f"{d.strftime('%b')} {d.day}"
    except ValueError:
        return iso_day


def destination_totals(orders: list[dict]) -> list[dict]:
    """Sum order totals by shipping state (delivery destination)."""
    buckets: dict[str, dict] = {}
    for raw in orders:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("OrderStatus") or "").strip().lower()
        if status == "canceled":
            continue
        ship = raw.get("ShippingAddress") or {}
        if not isinstance(ship, dict):
            continue
        state = str(ship.get("StateOrRegion") or "").strip()
        if not state:
            continue
        total = raw.get("OrderTotal") or {}
        amount = 0.0
        if isinstance(total, dict):
            try:
                amount = float(total.get("Amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
        key = state.casefold()
        row = buckets.get(key)
        if row is None:
            row = {"state": state, "amount": 0.0, "orderCount": 0}
            buckets[key] = row
        row["amount"] = round(row["amount"] + amount, 2)
        row["orderCount"] += 1
    return sorted(buckets.values(), key=lambda r: r["amount"], reverse=True)


def _to_chart_units(amount: float, currency: str) -> float:
    if currency == "INR":
        return round(amount / 100_000, 2)
    return round(amount / 1_000, 2)


def build_sales_trend_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise SalesTrendError("Sales trend is only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise SalesTrendError(
            "Connect your Amazon seller account before viewing sales trend"
        )

    today = datetime.now().date()
    default_start = today.replace(day=1)
    start = _parse_filter_date(date_from or "", default_start)
    end = _parse_filter_date(date_to or "", today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise SalesTrendError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    prev_start, prev_end = previous_period(start, end)

    try:
        current_sales, current_orders, currency = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=start,
            end=end,
        )
        previous_sales, previous_orders, _ = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=prev_start,
            end=prev_end,
        )
    except SpApiRequestError as exc:
        raise SalesTrendError(str(exc)) from exc

    destinations: list[dict] = []
    try:
        raw_orders = fetch_orders(
            access_token=access_token,
            marketplace_id=marketplace,
            created_after=created_after_from_start_date(start),
            created_before=created_before_from_end_date(end),
        )
        destinations = destination_totals(raw_orders)
    except SpApiRequestError:
        logger.warning("Sales trend destinations unavailable; chart data still returned")

    current_days = sorted(current_sales.keys())
    previous_days = sorted(previous_sales.keys())
    points = []
    for idx, day in enumerate(current_days):
        prev_day = previous_days[idx] if idx < len(previous_days) else None
        current_amount = current_sales.get(day, 0.0)
        prev_amount = (
            previous_sales.get(prev_day, 0.0) if prev_day is not None else 0.0
        )
        points.append(
            {
                "date": _format_point_label(day),
                "netSales": _to_chart_units(current_amount, currency),
                "netSalesAmount": round(current_amount, 2),
                "previousPeriod": _to_chart_units(prev_amount, currency),
                "previousPeriodAmount": round(prev_amount, 2),
                "orderCount": current_orders.get(day, 0),
                "previousPeriodOrderCount": (
                    previous_orders.get(prev_day, 0) if prev_day is not None else 0
                ),
            }
        )

    span_days = (end - start).days + 1
    frequency = "Daily" if span_days > 2 else "Hourly"

    return {
        "frequency": frequency,
        "currencySymbol": _CURRENCY_SYMBOLS.get(currency, currency),
        "points": points,
        "destinations": destinations,
    }
