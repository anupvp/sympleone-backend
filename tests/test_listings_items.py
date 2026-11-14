from datetime import date

from app.services.amazon.listings_items import (
    _normalize_listings_body,
    count_listings_created_between,
)


def test_normalize_listings_body_root_shape() -> None:
    data = {
        "numberOfResults": 89,
        "pagination": {"nextToken": "abc"},
        "items": [{"sku": "S1", "summaries": [{"status": ["BUYABLE"]}]}],
    }
    total, token, items = _normalize_listings_body(data)
    assert total == 89
    assert token == "abc"
    assert len(items) == 1


def test_count_listings_created_between() -> None:
    items = [
        {
            "summaries": [{"createdDate": "2026-09-15T10:00:00.000Z"}],
        },
        {
            "summaries": [{"createdDate": "2026-08-20T10:00:00.000Z"}],
        },
    ]
    assert (
        count_listings_created_between(
            items,
            start=date(2026, 9, 1),
            end=date(2026, 9, 30),
        )
        == 1
    )