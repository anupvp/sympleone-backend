"""Build top / low / summary product performance responses from persisted metrics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserKind
from app.services.amazon.sales_order_metrics import previous_period
from app.services.product_performance import repository as repo
from app.services.product_performance.growth import compute_growth, growth_sort_key


class ProductPerformanceQueryError(Exception):
    """Product performance could not be loaded."""


REVENUE_USES_SHIPPED_SALES = (
    "Revenue uses shipped product sales from the Sales & Traffic report when non-zero; "
    "otherwise ordered product sales (same source as Sales)."
)


def _parse_date(value: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return fallback


def _resolve_subject(user: User, seller: User | None) -> User:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise ProductPerformanceQueryError(
            "Product performance is only available for seller accounts"
        )
    return subject


def _revenue_amount(ordered_sales: float, shipped_sales: float) -> float:
    if shipped_sales > 0:
        return shipped_sales
    return ordered_sales


def _build_product_rows(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    current_end: date,
    prev_end: date,
    current_start: date,
    current_end_inclusive: date,
) -> list[dict[str, Any]]:
    current_rows = {
        r.sku: r
        for r in repo.load_daily_snapshot(
            db,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            report_date=current_end,
        )
    }
    previous_rows = {
        r.sku: r
        for r in repo.load_daily_snapshot(
            db,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            report_date=prev_end,
        )
    }

    all_skus = set(current_rows) | set(previous_rows)
    order_counts = repo.distinct_order_count_by_sku(
        db,
        seller_id=seller_id,
        marketplace_id=marketplace_id,
        start=current_start,
        end=current_end_inclusive,
    )
    titles = repo.product_titles_by_sku(
        db, seller_id=seller_id, marketplace_id=marketplace_id
    )

    products: list[dict[str, Any]] = []
    for sku in all_skus:
        current = current_rows.get(sku)
        previous = previous_rows.get(sku)
        current_sales = float(current.ordered_sales) if current else 0.0
        previous_sales = float(previous.ordered_sales) if previous else 0.0
        growth = compute_growth(current_sales, previous_sales)

        shipped = float(current.shipped_sales) if current else 0.0
        ordered = float(current.ordered_sales) if current else 0.0
        revenue = _revenue_amount(ordered, shipped)
        asin = (current.asin if current and current.asin else None) or (
            previous.asin if previous and previous.asin else None
        )

        name = titles.get(sku) or sku
        products.append(
            {
                "product_name": name,
                "sku": sku,
                "asin": asin,
                "sales": round(current_sales, 2),
                "orders": int(order_counts.get(sku, 0)),
                "revenue": round(revenue, 2),
                "growth_percentage": growth.growth_percentage,
                "growth_display": growth.growth_display,
                "currency": "INR",
                "_growth_sort": growth_sort_key(growth),
            }
        )
    return products


def _metadata(
    db: Session,
    *,
    seller_id: str,
    marketplace_id: str,
    start: date,
    end: date,
    prev_start: date,
    prev_end: date,
    total_products: int,
) -> dict[str, Any]:
    state = repo.get_or_create_sync_state(db, seller_id=seller_id, marketplace_id=marketplace_id)
    last_synced = (
        state.last_synced_at.isoformat() if state.last_synced_at is not None else None
    )
    return {
        "seller_id": seller_id,
        "marketplace_id": marketplace_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "comparison_start_date": prev_start.isoformat(),
        "comparison_end_date": prev_end.isoformat(),
        "last_synced_at": last_synced,
        "total_products": total_products,
        "revenue_definition": REVENUE_USES_SHIPPED_SALES,
    }


def list_top_products(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    subject = _resolve_subject(user, seller)
    today = datetime.now().date()
    default_start = today.replace(day=1)
    start = _parse_date(date_from, default_start)
    end = _parse_date(date_to, today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    prev_start, prev_end = previous_period(start, end)
    rows = _build_product_rows(
        db,
        seller_id=subject.id,
        marketplace_id=marketplace,
        current_end=end,
        prev_end=prev_end,
        current_start=start,
        current_end_inclusive=end,
    )
    rows.sort(key=lambda r: (-r["sales"], r["sku"]))
    trimmed = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows[: max(1, limit)]]

    return {
        "success": True,
        "data": trimmed,
        "metadata": _metadata(
            db,
            seller_id=subject.id,
            marketplace_id=marketplace,
            start=start,
            end=end,
            prev_start=prev_start,
            prev_end=prev_end,
            total_products=len(rows),
        ),
    }


def list_low_products(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    subject = _resolve_subject(user, seller)
    today = datetime.now().date()
    default_start = today.replace(day=1)
    start = _parse_date(date_from, default_start)
    end = _parse_date(date_to, today)
    if end < start:
        start, end = end, start

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    prev_start, prev_end = previous_period(start, end)
    rows = _build_product_rows(
        db,
        seller_id=subject.id,
        marketplace_id=marketplace,
        current_end=end,
        prev_end=prev_end,
        current_start=start,
        current_end_inclusive=end,
    )
    rows.sort(key=lambda r: (r["_growth_sort"], r["sales"], r["sku"]))
    trimmed = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows[: max(1, limit)]]

    return {
        "success": True,
        "data": trimmed,
        "metadata": _metadata(
            db,
            seller_id=subject.id,
            marketplace_id=marketplace,
            start=start,
            end=end,
            prev_start=prev_start,
            prev_end=prev_end,
            total_products=len(rows),
        ),
    }


def build_summary(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> dict[str, Any]:
    top = list_top_products(
        db,
        user,
        marketplace_id=marketplace_id,
        date_from=date_from,
        date_to=date_to,
        seller=seller,
        limit=5,
    )
    low = list_low_products(
        db,
        user,
        marketplace_id=marketplace_id,
        date_from=date_from,
        date_to=date_to,
        seller=seller,
        limit=5,
    )
    all_rows = _build_product_rows(
        db,
        seller_id=top["metadata"]["seller_id"],
        marketplace_id=top["metadata"]["marketplace_id"],
        current_end=_parse_date(top["metadata"]["end_date"], datetime.now().date()),
        prev_end=_parse_date(top["metadata"]["comparison_end_date"], datetime.now().date()),
        current_start=_parse_date(top["metadata"]["start_date"], datetime.now().date()),
        current_end_inclusive=_parse_date(top["metadata"]["end_date"], datetime.now().date()),
    )
    total_sales = round(sum(r["sales"] for r in all_rows), 2)
    total_orders = sum(r["orders"] for r in all_rows)
    total_revenue = round(sum(r["revenue"] for r in all_rows), 2)

    return {
        "success": True,
        "data": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "currency": "INR",
            "top_products": top["data"],
            "low_products": low["data"],
        },
        "metadata": top["metadata"],
    }