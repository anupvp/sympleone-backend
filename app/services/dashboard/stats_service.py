"""Dashboard stat cards (GMV and future metrics) from Amazon order metrics."""

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


class DashboardStatsError(Exception):
    """Stat cards could not be produced for the dashboard."""


_CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

_MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _parse_filter_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return fallback


def _format_short_date(d: date) -> str:
    return f"{_MONTH_NAMES[d.month - 1]} {d.day}, {d.year}"


def _comparison_label(prev_start: date, prev_end: date) -> str:
    return f"vs {_format_short_date(prev_start)} – {_format_short_date(prev_end)}"


def _format_compact_currency(amount: float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    abs_amount = abs(amount)
    if currency == "INR":
        if abs_amount >= 10_000_000:
            return f"{symbol}{amount / 10_000_000:.1f}Cr"
        if abs_amount >= 100_000:
            return f"{symbol}{amount / 100_000:.1f}L"
        if abs_amount >= 1_000:
            return f"{symbol}{amount / 1_000:.1f}K"
        rounded = round(amount)
        return f"{symbol}{rounded:,}"

    if abs_amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.1f}M"
    if abs_amount >= 1_000:
        return f"{symbol}{amount / 1_000:.1f}K"
    rounded = round(amount, 2)
    return f"{symbol}{rounded:,.2f}"


def _percent_change(current: float, previous: float) -> float:
    if previous > 0:
        return round(((current - previous) / previous) * 100, 1)
    if current > 0:
        return 100.0
    return 0.0


def _sum_sales(sales_by_day: dict[str, float]) -> float:
    return sum(sales_by_day.values())


def build_dashboard_stats_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> list[dict]:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise DashboardStatsError("Dashboard stats are only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise DashboardStatsError(
            "Connect your Amazon seller account before viewing dashboard stats"
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
        raise DashboardStatsError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    prev_start, prev_end = previous_period(start, end)

    try:
        current_sales, _, currency = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=start,
            end=end,
        )
        previous_sales, _, _ = fetch_order_metrics(
            access_token=access_token,
            marketplace_id=marketplace,
            start=prev_start,
            end=prev_end,
        )
    except SpApiRequestError as exc:
        raise DashboardStatsError(str(exc)) from exc

    current_gmv = _sum_sales(current_sales)
    previous_gmv = _sum_sales(previous_sales)

    return [
        {
            "id": "gmv",
            "label": "SALES",
            "value": _format_compact_currency(current_gmv, currency),
            "changePercent": _percent_change(current_gmv, previous_gmv),
            "comparisonLabel": _comparison_label(prev_start, prev_end),
            "icon": "gmv",
            "accent": "purple",
        },
    ]
