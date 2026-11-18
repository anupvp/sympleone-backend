"""Amazon Finances API (2024-06-19) — list transactions for settlement totals."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from dataclasses import dataclass
from typing import Any

from app.services.amazon.sp_api_client import sp_api_get
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

TRANSACTIONS_PATH = "/finances/2024-06-19/transactions"
_MAX_TRANSACTION_PAGES = 40


@dataclass(frozen=True)
class FinanceFetchResult:
    transactions: list[dict[str, Any]]
    truncated: bool


def posted_after_from_start_date(d: date) -> str:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def posted_before_from_end_date(end: date) -> str:
    next_day = end + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_posted_date(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def _transaction_amount(row: dict[str, Any]) -> tuple[float, str]:
    total = row.get("totalAmount") or {}
    amount = total.get("currencyAmount")
    code = str(total.get("currencyCode") or "INR")
    try:
        return float(amount or 0.0), code
    except (TypeError, ValueError):
        return 0.0, code


def _inclusive_date_range(start: date, end: date, posted: datetime) -> bool:
    day = posted.date()
    return start <= day <= end


def fetch_finance_transactions_result(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> FinanceFetchResult:
    host = sp_api_host_for_marketplace(marketplace_id)
    query: dict[str, str] = {
        "marketplaceId": marketplace_id,
        "postedAfter": posted_after_from_start_date(start),
        "postedBefore": posted_before_from_end_date(end),
    }

    rows: list[dict[str, Any]] = []
    next_token: str | None = None
    pages = 0

    while pages < _MAX_TRANSACTION_PAGES:
        page_query = dict(query)
        if next_token:
            page_query["nextToken"] = next_token

        data = sp_api_get(
            host=host,
            path=TRANSACTIONS_PATH,
            query=page_query,
            access_token=access_token,
        )
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        batch = payload.get("transactions") if isinstance(payload.get("transactions"), list) else []
        for item in batch:
            if isinstance(item, dict):
                rows.append(item)

        next_token = payload.get("nextToken") or data.get("nextToken")
        if isinstance(next_token, str):
            next_token = next_token.strip() or None
        else:
            next_token = None

        pages += 1
        if not next_token:
            break

    truncated = bool(pages >= _MAX_TRANSACTION_PAGES and next_token)
    if truncated:
        logger.warning(
            "Finance transactions pagination truncated at %s rows for %s–%s",
            len(rows),
            start,
            end,
        )

    return FinanceFetchResult(transactions=rows, truncated=truncated)


def fetch_finance_transactions(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    return fetch_finance_transactions_result(
        access_token=access_token,
        marketplace_id=marketplace_id,
        start=start,
        end=end,
    ).transactions


def sum_released_finance_net(
    transactions: list[dict[str, Any]],
    *,
    start: date,
    end: date,
) -> tuple[float, str]:
    """
    Sum totalAmount for RELEASED transactions whose postedDate falls in [start, end].
    """
    total = 0.0
    currency = "INR"
    for row in transactions:
        if not isinstance(row, dict):
            continue
        status = str(row.get("transactionStatus") or "").strip().upper()
        if status and status != "RELEASED":
            continue
        posted_raw = row.get("postedDate")
        if isinstance(posted_raw, str):
            posted = _parse_posted_date(posted_raw)
            if posted is None or not _inclusive_date_range(start, end, posted):
                continue
        amount, code = _transaction_amount(row)
        total += amount
        if code:
            currency = code
    return total, currency
