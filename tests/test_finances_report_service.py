from datetime import date

from app.services.reports.finances_report_service import _aggregate_report_rows


def test_aggregate_finances_report_groups_daily_and_types() -> None:
    rows = [
        {
            "transactionId": "a",
            "transactionType": "Shipment",
            "transactionStatus": "RELEASED",
            "postedDate": "2026-10-15T12:00:00Z",
            "totalAmount": {"currencyAmount": 100.0, "currencyCode": "INR"},
            "relatedIdentifiers": [
                {"relatedIdentifierName": "ORDER_ID", "relatedIdentifierValue": "1"},
            ],
        },
        {
            "transactionId": "b",
            "transactionType": "ServiceFee",
            "transactionStatus": "RELEASED",
            "postedDate": "2026-10-15T18:00:00Z",
            "totalAmount": {"currencyAmount": -10.0, "currencyCode": "INR"},
            "relatedIdentifiers": [],
        },
        {
            "transactionId": "c",
            "transactionType": "Shipment",
            "transactionStatus": "RELEASED",
            "postedDate": "2026-09-01T12:00:00Z",
            "totalAmount": {"currencyAmount": 999.0, "currencyCode": "INR"},
            "relatedIdentifiers": [],
        },
    ]
    start = date(2026, 10, 14)
    end = date(2026, 10, 16)
    transactions, daily, by_type, currency = _aggregate_report_rows(rows, start=start, end=end)
    assert currency == "INR"
    assert len(transactions) == 2
    assert transactions[0]["transactionId"] == "b"
    assert transactions[0]["orderId"] is None
    assert transactions[1]["orderId"] == "1"
    day_15 = next(p for p in daily if p["date"] == "2026-10-15")
    assert day_15["netAmount"] == 90.0
    assert day_15["count"] == 2
    assert len(by_type) == 2
    shipment = next(t for t in by_type if t["transactionType"] == "Shipment")
    assert shipment["totalAmount"] == 100.0