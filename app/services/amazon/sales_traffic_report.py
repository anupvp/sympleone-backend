"""Sales and Traffic report — create, download, and parse SKU-level metrics."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.amazon.reports_api import (
    create_report,
    download_report_document,
    get_report_document,
    report_data_end_time,
    report_data_start_time,
    wait_until_report_done,
)
from app.services.amazon.sp_api_client import SpApiRequestError

logger = logging.getLogger(__name__)

SALES_TRAFFIC_REPORT_TYPE = "GET_SALES_AND_TRAFFIC_REPORT"

SALES_TRAFFIC_REPORT_OPTIONS = {
    "dateGranularity": "DAY",
    "asinGranularity": "SKU",
}


@dataclass(frozen=True)
class SkuSalesTrafficRow:
    sku: str
    asin: str | None
    units_ordered: int
    ordered_sales: float
    currency: str
    total_order_items: int
    units_shipped: int
    shipped_sales: float


def _money_amount(block: Any) -> tuple[float, str]:
    if not isinstance(block, dict):
        return 0.0, "INR"
    amount_raw = block.get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    currency = str(block.get("currencyCode") or "INR").strip() or "INR"
    return amount, currency


def _int_field(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def parse_sales_and_traffic_by_asin(payload: dict[str, Any]) -> list[SkuSalesTrafficRow]:
    """Extract SKU rows from a Sales & Traffic JSON document (defensive parsing)."""
    rows_raw = payload.get("salesAndTrafficByAsin")
    if not isinstance(rows_raw, list):
        logger.warning("salesAndTrafficByAsin missing or not a list")
        return []

    parsed: list[SkuSalesTrafficRow] = []
    for entry in rows_raw:
        if not isinstance(entry, dict):
            continue
        sku = str(entry.get("sku") or entry.get("sellerSku") or "").strip()
        if not sku:
            continue
        asin_raw = entry.get("childAsin") or entry.get("parentAsin") or entry.get("asin")
        asin = str(asin_raw).strip() if asin_raw else None

        sales_by = entry.get("salesByAsin")
        if not isinstance(sales_by, dict):
            sales_by = entry.get("salesBySku") if isinstance(entry.get("salesBySku"), dict) else {}

        ordered_amount, currency = _money_amount(sales_by.get("orderedProductSales"))
        shipped_amount, _ = _money_amount(sales_by.get("shippedProductSales"))

        parsed.append(
            SkuSalesTrafficRow(
                sku=sku,
                asin=asin,
                units_ordered=_int_field(sales_by.get("unitsOrdered")),
                ordered_sales=ordered_amount,
                currency=currency,
                total_order_items=_int_field(sales_by.get("totalOrderItems")),
                units_shipped=_int_field(sales_by.get("unitsShipped")),
                shipped_sales=shipped_amount,
            )
        )
    return parsed


def fetch_sales_and_traffic_report(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    report_id = create_report(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_type=SALES_TRAFFIC_REPORT_TYPE,
        data_start=report_data_start_time(start),
        data_end=report_data_end_time(end),
        report_options=SALES_TRAFFIC_REPORT_OPTIONS,
    )
    logger.info("Created Sales & Traffic report id=%s", report_id)

    done = wait_until_report_done(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_id=report_id,
    )
    document_id = done.get("reportDocumentId")
    if not document_id:
        raise SpApiRequestError("Sales & Traffic report completed without a document id")

    doc = get_report_document(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_document_id=str(document_id),
    )
    url = doc.get("url")
    if not isinstance(url, str) or not url.strip():
        raise SpApiRequestError("Sales & Traffic report document did not include a download URL")

    compression = doc.get("compressionAlgorithm")
    comp = compression.strip() if isinstance(compression, str) and compression.strip() else None
    raw = download_report_document(url.strip(), compression=comp)

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SpApiRequestError("Sales & Traffic report is not valid UTF-8 JSON") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpApiRequestError("Sales & Traffic report is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise SpApiRequestError("Sales & Traffic report JSON root is not an object")

    return payload