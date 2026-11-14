from unittest.mock import patch

from app.services.amazon.reports_api import (
    fetch_merchant_listings_report_file,
    wait_until_report_done,
)


@patch("app.services.amazon.reports_api.time.sleep")
@patch("app.services.amazon.reports_api.get_report")
def test_wait_until_report_done(mock_get_report, _mock_sleep) -> None:
    mock_get_report.side_effect = [
        {"processingStatus": "IN_PROGRESS"},
        {"processingStatus": "DONE", "reportDocumentId": "doc-1"},
    ]
    row = wait_until_report_done(
        access_token="token",
        marketplace_id="A21TJRUUN4KGV",
        report_id="62734020771",
    )
    assert row["reportDocumentId"] == "doc-1"


@patch("app.services.amazon.reports_api.download_report_document")
@patch("app.services.amazon.reports_api.get_report_document")
@patch("app.services.amazon.reports_api.wait_until_report_done")
@patch("app.services.amazon.reports_api.create_report")
def test_fetch_merchant_listings_report_file(
    mock_create,
    mock_wait,
    mock_doc,
    mock_download,
) -> None:
    from datetime import date

    mock_create.return_value = "62734020771"
    mock_wait.return_value = {"reportDocumentId": "amzn1.doc"}
    mock_doc.return_value = {
        "url": "https://example.com/report",
        "compressionAlgorithm": "GZIP",
    }
    mock_download.return_value = b"sku\tasin\n"

    data = fetch_merchant_listings_report_file(
        access_token="token",
        marketplace_id="A21TJRUUN4KGV",
        start=date(2026, 9, 1),
        end=date(2026, 9, 30),
    )
    assert data == b"sku\tasin\n"
    mock_create.assert_called_once()
    mock_download.assert_called_once_with(
        "https://example.com/report",
        compression="GZIP",
    )