from datetime import date

from app.services.amazon.orders_api import _iso_created_after, _iso_created_before_exclusive


def test_created_after_iso():
    assert _iso_created_after(date(2026, 9, 1)) == "2026-09-01T00:00:00Z"


def test_created_before_exclusive():
    assert _iso_created_before_exclusive(date(2026, 9, 30)) == "2026-10-01T00:00:00Z"
