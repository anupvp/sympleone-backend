"""Dashboard export — merchant listings report download."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.reports_api import (
    ReportProcessingError,
    fetch_merchant_listings_report_file,
)
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError


class DashboardExportError(Exception):
    """Report export failed."""


def _parse_filter_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return fallback


def export_merchant_listings_report_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    date_from: str | None,
    date_to: str | None,
    seller: User | None = None,
) -> tuple[bytes, str]:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise DashboardExportError("Reports are only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise DashboardExportError(
            "Connect your Amazon seller account before downloading reports"
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
        raise DashboardExportError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    try:
        content = fetch_merchant_listings_report_file(
            access_token=access_token,
            marketplace_id=marketplace,
            start=start,
            end=end,
        )
    except ReportProcessingError as exc:
        raise DashboardExportError(str(exc)) from exc
    except SpApiRequestError as exc:
        raise DashboardExportError(str(exc)) from exc

    filename = f"merchant-listings-{start.isoformat()}-to-{end.isoformat()}.txt"
    return content, filename