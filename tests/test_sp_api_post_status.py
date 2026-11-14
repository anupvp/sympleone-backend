import json
from unittest.mock import MagicMock, patch

from app.services.amazon.sp_api_client import sp_api_post


@patch("app.services.amazon.sp_api_client.httpx.Client")
def test_sp_api_post_accepts_202(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {"reportId": "62737020771"}
    mock_response.text = '{"reportId":"62737020771"}'
    mock_client.post.return_value = mock_response

    data = sp_api_post(
        host="sellingpartnerapi-eu.amazon.com",
        path="/reports/2021-06-30/reports",
        body={"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA"},
        access_token="atza-token",
    )
    assert data["reportId"] == "62737020771"
    mock_client.post.assert_called_once()
    call_kw = mock_client.post.call_args.kwargs
    assert call_kw["content"] == json.dumps(
        {"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA"}
    ).encode("utf-8")