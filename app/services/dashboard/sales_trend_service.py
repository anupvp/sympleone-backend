"""Build dashboard sales trend from Amazon order metrics."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.sales_order_metrics import fetch_order_metrics, previous_period
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError


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
) -> dict:
    if user.kind != UserKind.SELLER:
        raise SalesTrendError("Sales trend is only available for seller accounts")

    connection = find_active_connection_for_user(db, user.id)
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
        current_buckets, currency = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=start,
            end=end,
        )
        previous_buckets, _ = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=prev_start,
            end=prev_end,
        )
    except SpApiRequestError as exc:
        raise SalesTrendError(str(exc)) from exc

    current_days = sorted(current_buckets.keys())
    previous_days = sorted(previous_buckets.keys())
    points = []
    for idx, day in enumerate(current_days):
        prev_amount = 0.0
        if idx < len(previous_days):
            prev_amount = previous_buckets.get(previous_days[idx], 0.0)
        points.append(
            {
                "date": _format_point_label(day),
                "netSales": _to_chart_units(current_buckets.get(day, 0.0), currency),
                "previousPeriod": _to_chart_units(prev_amount, currency),
            }
        )

    span_days = (end - start).days + 1
    frequency = "Daily" if span_days > 2 else "Hourly"

    return {
        "frequency": frequency,
        "currencySymbol": _CURRENCY_SYMBOLS.get(currency, currency),
        "points": points,
    }
