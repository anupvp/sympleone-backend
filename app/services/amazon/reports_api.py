"""Amazon Reports API — create, poll, and download report documents."""

from __future__ import annotations

import gzip
import logging
import time
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.services.amazon.sp_api_client import (
    SP_API_REPORT_TIMEOUT_SECONDS,
    SpApiRequestError,
    sp_api_get,
    sp_api_post,
)
from app.services.amazon.sp_api_endpoints import sp_api_host_for_marketplace

logger = logging.getLogger(__name__)

REPORTS_VERSION = "2021-06-30"
REPORTS_COLLECTION = f"/reports/{REPORTS_VERSION}/reports"
MERCHANT_LISTINGS_REPORT_TYPE = "GET_MERCHANT_LISTINGS_ALL_DATA"

REPORT_POLL_INTERVAL_SECONDS = 5.0
REPORT_MAX_WAIT_SECONDS = 600.0


class ReportProcessingError(Exception):
    """Report could not be generated."""


def report_data_start_time(start: date) -> str:
    return datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def report_data_end_time(end: date) -> str:
    return datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload")
    if isinstance(payload, dict):
        return payload
    return data


def create_report(
    *,
    access_token: str,
    marketplace_id: str,
    report_type: str,
    data_start: str,
    data_end: str,
) -> str:
    host = sp_api_host_for_marketplace(marketplace_id)
    body = {
        "marketplaceIds": [marketplace_id],
        "reportType": report_type,
        "dataStartTime": data_start,
        "dataEndTime": data_end,
    }
    data = sp_api_post(
        host=host,
        path=REPORTS_COLLECTION,
        body=body,
        access_token=access_token,
        timeout=SP_API_REPORT_TIMEOUT_SECONDS,
    )
    report_id = data.get("reportId") or _unwrap_payload(data).get("reportId")
    if not report_id:
        raise SpApiRequestError("Amazon did not return a report id")
    return str(report_id)


def get_report(
    *,
    access_token: str,
    marketplace_id: str,
    report_id: str,
) -> dict[str, Any]:
    host = sp_api_host_for_marketplace(marketplace_id)
    path = f"{REPORTS_COLLECTION}/{quote(report_id, safe='')}"
    data = sp_api_get(
        host=host,
        path=path,
        query=None,
        access_token=access_token,
        timeout=SP_API_REPORT_TIMEOUT_SECONDS,
    )
    return _unwrap_payload(data)


def wait_until_report_done(
    *,
    access_token: str,
    marketplace_id: str,
    report_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + REPORT_MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        row = get_report(
            access_token=access_token,
            marketplace_id=marketplace_id,
            report_id=report_id,
        )
        status = str(row.get("processingStatus") or "").strip().upper()
        if status == "DONE":
            return row
        if status in {"CANCELLED", "FATAL"}:
            raise ReportProcessingError(
                f"Amazon report processing failed ({status or 'unknown'})"
            )
        time.sleep(REPORT_POLL_INTERVAL_SECONDS)
    raise ReportProcessingError("Timed out waiting for Amazon report")


def get_report_document(
    *,
    access_token: str,
    marketplace_id: str,
    report_document_id: str,
) -> dict[str, Any]:
    host = sp_api_host_for_marketplace(marketplace_id)
    path = f"/reports/{REPORTS_VERSION}/documents/{quote(report_document_id, safe='')}"
    data = sp_api_get(
        host=host,
        path=path,
        query=None,
        access_token=access_token,
        timeout=SP_API_REPORT_TIMEOUT_SECONDS,
    )
    return _unwrap_payload(data)


def download_report_document(url: str, *, compression: str | None) -> bytes:
    try:
        with httpx.Client(timeout=SP_API_REPORT_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("Report document download failed: %s", type(exc).__name__)
        raise SpApiRequestError("Could not download report file from Amazon") from exc

    if response.status_code != 200:
        raise SpApiRequestError(
            f"Report file download failed (HTTP {response.status_code})",
            status_code=response.status_code,
        )

    raw = response.content
    algo = str(compression or "").strip().upper()
    if algo == "GZIP":
        try:
            return gzip.decompress(raw)
        except OSError as exc:
            raise SpApiRequestError("Report file could not be decompressed") from exc
    return raw


def fetch_merchant_listings_report_file(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
) -> bytes:
    report_id = create_report(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_type=MERCHANT_LISTINGS_REPORT_TYPE,
        data_start=report_data_start_time(start),
        data_end=report_data_end_time(end),
    )
    logger.info("Created Amazon report id=%s type=%s", report_id, MERCHANT_LISTINGS_REPORT_TYPE)

    done = wait_until_report_done(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_id=report_id,
    )
    document_id = done.get("reportDocumentId")
    if not document_id:
        raise SpApiRequestError("Amazon report completed without a document id")

    doc = get_report_document(
        access_token=access_token,
        marketplace_id=marketplace_id,
        report_document_id=str(document_id),
    )
    url = doc.get("url")
    if not isinstance(url, str) or not url.strip():
        raise SpApiRequestError("Amazon report document did not include a download URL")

    compression = doc.get("compressionAlgorithm")
    comp = compression.strip() if isinstance(compression, str) and compression.strip() else None
    return download_report_document(url.strip(), compression=comp)