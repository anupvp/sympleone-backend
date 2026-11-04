from datetime import date

from app.services.amazon.finance_transactions import sum_released_finance_net


def test_sum_released_finance_net_filters_status_and_dates() -> None:
    rows = [
        {
            "transactionStatus": "RELEASED",
            "postedDate": "2026-10-15T12:00:00Z",
            "totalAmount": {"currencyAmount": 936.64, "currencyCode": "INR"},
        },
        {
            "transactionStatus": "RELEASED",
            "postedDate": "2026-10-16T08:00:00Z",
            "totalAmount": {"currencyAmount": -88.5, "currencyCode": "INR"},
        },
        {
            "transactionStatus": "DEFERRED",
            "postedDate": "2026-10-16T08:00:00Z",
            "totalAmount": {"currencyAmount": 500.0, "currencyCode": "INR"},
        },
        {
            "transactionStatus": "RELEASED",
            "postedDate": "2026-09-30T23:59:59Z",
            "totalAmount": {"currencyAmount": 100.0, "currencyCode": "INR"},
        },
    ]
    total, currency = sum_released_finance_net(
        rows,
        start=date(2026, 10, 1),
        end=date(2026, 10, 31),
    )
    assert currency == "INR"
    assert round(total, 2) == round(936.64 - 88.5, 2)
