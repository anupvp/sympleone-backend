from unittest.mock import patch

from app.services.amazon.marketplace_resolver import normalize_marketplace_for_seller


@patch("app.services.amazon.marketplace_resolver.list_seller_marketplace_ids")
def test_uses_requested_when_seller_participates(mock_list) -> None:
    mock_list.return_value = ["ATVPDKIKX0DER", "A21TJRUUN4KGV"]
    assert (
        normalize_marketplace_for_seller("tok", "ATVPDKIKX0DER", default="A21TJRUUN4KGV")
        == "ATVPDKIKX0DER"
    )


@patch("app.services.amazon.marketplace_resolver.list_seller_marketplace_ids")
def test_falls_back_when_seller_not_in_india(mock_list) -> None:
    mock_list.return_value = ["ATVPDKIKX0DER"]
    assert (
        normalize_marketplace_for_seller("tok", "A21TJRUUN4KGV", default="A21TJRUUN4KGV")
        == "ATVPDKIKX0DER"
    )


@patch("app.services.amazon.marketplace_resolver.list_seller_marketplace_ids")
def test_uses_default_when_participations_empty(mock_list) -> None:
    mock_list.return_value = []
    assert normalize_marketplace_for_seller("tok", "all", default="A21TJRUUN4KGV") == "A21TJRUUN4KGV"