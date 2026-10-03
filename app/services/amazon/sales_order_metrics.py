"""Fetch order metrics from the Sales API."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

ORDER_METRICS_PATH = "/sales/v1/orderMetrics"


def _amazon_interval(start: date, end: date) -> str:
    start_iso = datetime(start.year, start.month, start.day, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    end_iso = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return f"{start_iso}--{end_iso}"


def _parse_interval_start(interval: str) -> date:
    start = interval.split("--", 1)[0]
    return datetime.fromisoformat(start.replace("Z", "+00:00")).date()


def _metric_sales_amount(row: dict[str, Any]) -> float:
    total_sales = row.get("totalSales") or {}
    amount = total_sales.get("amount")
    if amount is None:
        return 0.0
    try:
        return float(amount)
    except (TypeError, ValueError):
        return 0.0


def _metric_order_count(row: dict[str, Any]) -> int:
    count = row.get("orderCount")
    if count is None:
        return 0
    try:
        return int(count)
    except (TypeError, ValueError):
        return 0


def _metric_currency(row: dict[str, Any]) -> str:
    total_sales = row.get("totalSales") or {}
    code = total_sales.get("currencyCode")
    return str(code or "INR")


def _choose_granularity(start: date, end: date) -> str:
    days = (end - start).days + 1
    if days <= 2:
        return "Hour"
    return "Day"


def _bucket_key(row: dict[str, Any], granularity: str) -> str:
    interval = str(row.get("interval") or "")
    if granularity == "Hour":
        return _parse_interval_start(interval).isoformat()
    return _parse_interval_start(interval).isoformat()


def _aggregate_payload(
    rows: list[dict[str, Any]], granularity: str
) -> tuple[dict[str, float], dict[str, int]]:
    sales: dict[str, float] = {}
    orders: dict[str, int] = {}
    for row in rows:
        key = _bucket_key(row, granularity)
        sales[key] = sales.get(key, 0.0) + _metric_sales_amount(row)
        orders[key] = orders.get(key, 0) + _metric_order_count(row)
    return sales, orders


def fetch_order_metrics(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
    granularity: str | None = None,
) -> tuple[dict[str, float], dict[str, int], str]:
    """
    Return sales totals and order counts keyed by ISO date, plus currency code.
    """
    gran = granularity or _choose_granularity(start, end)
    host = sp_api_host_for_marketplace(marketplace_id)
    query = {
        "marketplaceIds": marketplace_id,
        "interval": _amazon_interval(start, end),
        "granularity": gran,
    }
    data = sp_api_get(
        host=host,
        path=ORDER_METRICS_PATH,
        query=query,
        access_token=access_token,
    )
    payload = data.get("payload") or []
    if not isinstance(payload, list):
        payload = []

    currency = "INR"
    if payload:
        currency = _metric_currency(payload[0])

    if gran == "Hour":
        daily_sales: dict[str, float] = {}
        daily_orders: dict[str, int] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            day_key = _parse_interval_start(str(row.get("interval") or "")).isoformat()
            daily_sales[day_key] = daily_sales.get(day_key, 0.0) + _metric_sales_amount(
                row
            )
            daily_orders[day_key] = daily_orders.get(day_key, 0) + _metric_order_count(
                row
            )
        return daily_sales, daily_orders, currency

    sales_buckets, order_buckets = _aggregate_payload(
        [r for r in payload if isinstance(r, dict)], gran
    )
    return sales_buckets, order_buckets, currency


def previous_period(start: date, end: date) -> tuple[date, date]:
    span_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)
    return prev_start, prev_end
