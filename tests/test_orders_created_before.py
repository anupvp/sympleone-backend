from datetime import UTC, datetime, timedelta

from app.services.amazon.orders_api import normalize_created_before


def test_normalize_created_before_caps_future_date():
    future = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    capped = normalize_created_before(future)
    capped_dt = datetime.fromisoformat(capped.replace("Z", "+00:00"))
    assert capped_dt <= datetime.now(UTC) - timedelta(minutes=2)


def test_normalize_created_before_keeps_past_date():
    past = "2026-09-30T00:00:00Z"
    assert normalize_created_before(past) == past
