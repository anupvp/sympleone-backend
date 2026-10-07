from datetime import date

from app.services.amazon.orders_api import created_after_from_start_date, created_before_from_end_date


def test_created_after_matches_postman_pattern():
    assert created_after_from_start_date(date(2026, 9, 1)) == "2026-09-01T23:59:59Z"


def test_created_before_matches_postman_pattern():
    assert created_before_from_end_date(date(2026, 9, 30)) == "2026-10-01T00:00:00Z"
