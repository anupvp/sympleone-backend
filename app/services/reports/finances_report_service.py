"""Finances report: transactions list and chart series from SP-API Finances."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.finance_transactions import (
    _inclusive_date_range,
    _parse_posted_date,
    _transaction_amount,
    fetch_finance_transactions_result,
)
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError

_REF_NAMES = (
    "ORDER_ID",
    "SETTLEMENT_ID",
    "SHIPMENT_ID",
    "FINANCIAL_EVENT_GROUP_ID",
)


class FinancesReportError(Exception):
    """Finances report could not be built."""


def _parse_filter_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return fallback


def _related_value(row: dict, name: str) -> str | None:
    identifiers = row.get("relatedIdentifiers")
    if not isinstance(identifiers, list):
        return None
    for item in identifiers:
        if not isinstance(item, dict):
            continue
        if str(item.get("relatedIdentifierName") or "") == name:
            raw = item.get("relatedIdentifierValue")
            if raw is None:
                return None
            text = str(raw).strip()
            return text or None
    return None


def _normalize_transaction(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    txn_id = str(row.get("transactionId") or "").strip()
    if not txn_id:
        return None
    amount, currency = _transaction_amount(row)
    posted_raw = row.get("postedDate")
    posted = str(posted_raw) if isinstance(posted_raw, str) else ""
    return {
        "transactionId": txn_id,
        "transactionType": str(row.get("transactionType") or "Unknown"),
        "transactionStatus": str(row.get("transactionStatus") or "") or None,
        "description": (
            str(row.get("description")).strip()
            if row.get("description") is not None
            else None
        ),
        "postedDate": posted,
        "amount": round(amount, 2),
        "currencyCode": currency,
        "orderId": _related_value(row, "ORDER_ID"),
        "settlementId": _related_value(row, "SETTLEMENT_ID"),
        "shipmentId": _related_value(row, "SHIPMENT_ID"),
        "eventGroupId": _related_value(row, "FINANCIAL_EVENT_GROUP_ID"),
    }


def _aggregate_report_rows(
    raw_rows: list[dict],
    *,
    start: date,
    end: date,
) -> tuple[list[dict], list[dict], list[dict], str]:
    transactions: list[dict] = []
    daily: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    by_type: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    currency = "INR"

    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        posted_raw = row.get("postedDate")
        if not isinstance(posted_raw, str):
            continue
        posted = _parse_posted_date(posted_raw)
        if posted is None or not _inclusive_date_range(start, end, posted):
            continue

        normalized = _normalize_transaction(row)
        if normalized is None:
            continue
        transactions.append(normalized)

        day_key = posted.date().isoformat()
        amount, code = _transaction_amount(row)
        if code:
            currency = code
        prev_sum, prev_count = daily[day_key]
        daily[day_key] = (prev_sum + amount, prev_count + 1)

        txn_type = str(row.get("transactionType") or "Unknown")
        t_sum, t_count = by_type[txn_type]
        by_type[txn_type] = (t_sum + amount, t_count + 1)

    transactions.sort(key=lambda t: t.get("postedDate") or "", reverse=True)

    daily_series: list[dict] = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        net, count = daily.get(key, (0.0, 0))
        daily_series.append(
            {
                "date": key,
                "netAmount": round(net, 2),
                "count": count,
            }
        )
        cursor += timedelta(days=1)

    type_breakdown = [
        {
            "transactionType": name,
            "totalAmount": round(values[0], 2),
            "count": values[1],
        }
        for name, values in sorted(
            by_type.items(),
            key=lambda item: abs(item[1][0]),
            reverse=True,
        )
    ]

    return transactions, daily_series, type_breakdown, currency


def build_finances_report_for_user(
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
        raise FinancesReportError("Finances are only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise FinancesReportError(
            "Connect your Amazon seller account before viewing finances"
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
        raise FinancesReportError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    try:
        fetch_result = fetch_finance_transactions_result(
            access_token=access_token,
            marketplace_id=marketplace,
            start=start,
            end=end,
        )
    except SpApiRequestError as exc:
        raise FinancesReportError(str(exc)) from exc

    transactions, daily_series, by_type, currency = _aggregate_report_rows(
        fetch_result.transactions,
        start=start,
        end=end,
    )

    return {
        "currencyCode": currency,
        "dateFrom": start.isoformat(),
        "dateTo": end.isoformat(),
        "truncated": fetch_result.truncated,
        "transactions": transactions,
        "dailySeries": daily_series,
        "byType": by_type,
    }