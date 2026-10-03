from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import httpx
import pytest

from app.config import settings
from app.services.amazon.lwa_token_service import (
    LWA_REQUEST_TIMEOUT_SECONDS,
    LWA_TOKEN_CONTENT_TYPE,
    LwaConfigurationError,
    LwaTokenExchangeError,
    exchange_authorization_code,
)

DEFAULT_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

AUTH_CODE = "Atza|SpApiAuthCodeExample"
REDIRECT_URI = "https://sympleone-api.onrender.com/api/amazon/callback"
CLIENT_ID = "amzn1.application-oa2-client.test"
CLIENT_SECRET = "test-client-secret-do-not-log"


@pytest.fixture(autouse=True)
def _lwa_env() -> None:
    settings.amazon_client_id = CLIENT_ID
    settings.amazon_client_secret = CLIENT_SECRET
    settings.amazon_redirect_uri = REDIRECT_URI


def _mock_httpx_client(post_return: MagicMock) -> MagicMock:
    client_ctx = MagicMock()
    client_ctx.__enter__.return_value.post.return_value = post_return
    return client_ctx


def test_successful_authorization_code_exchange() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "access_token": "short-lived-access",
        "refresh_token": "long-lived-refresh",
        "token_type": "bearer",
        "expires_in": 3600,
        "scope": "sellingpartnerapi::notifications",
    }
    with patch("app.services.amazon.lwa_token_service.httpx.Client") as client_cls:
        client_cls.return_value = _mock_httpx_client(response)
        result = exchange_authorization_code(AUTH_CODE)
        post = client_cls.return_value.__enter__.return_value.post

    assert result == {
        "access_token": "short-lived-access",
        "refresh_token": "long-lived-refresh",
        "token_type": "bearer",
        "expires_in": 3600,
    }
    assert "scope" not in result

    expected_body = urlencode(
        [
            ("grant_type", "authorization_code"),
            ("code", AUTH_CODE),
            ("redirect_uri", REDIRECT_URI),
            ("client_id", CLIENT_ID),
            ("client_secret", CLIENT_SECRET),
        ]
    ).encode("utf-8")
    post.assert_called_once_with(
        DEFAULT_LWA_TOKEN_URL,
        content=expected_body,
        headers={"Content-Type": LWA_TOKEN_CONTENT_TYPE},
    )
    assert client_cls.call_args.kwargs["timeout"] == LWA_REQUEST_TIMEOUT_SECONDS


def test_amazon_rejects_invalid_authorization_code() -> None:
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {"error": "invalid_grant"}
    with patch("app.services.amazon.lwa_token_service.httpx.Client", return_value=_mock_httpx_client(response)):
        with pytest.raises(LwaTokenExchangeError, match="rejected"):
            exchange_authorization_code(AUTH_CODE)


def test_amazon_returns_http_error_status() -> None:
    response = MagicMock()
    response.status_code = 503
    with patch("app.services.amazon.lwa_token_service.httpx.Client", return_value=_mock_httpx_client(response)):
        with pytest.raises(LwaTokenExchangeError, match="rejected"):
            exchange_authorization_code(AUTH_CODE)


def test_missing_environment_variables() -> None:
    settings.amazon_client_secret = None
    with pytest.raises(LwaConfigurationError, match="AMAZON_CLIENT_SECRET"):
        exchange_authorization_code(AUTH_CODE)


def test_amazon_timeout_or_network_failure() -> None:
    client_ctx = MagicMock()
    client_ctx.__enter__.return_value.post.side_effect = httpx.ConnectError("connection refused")
    with patch("app.services.amazon.lwa_token_service.httpx.Client", return_value=client_ctx):
        with pytest.raises(LwaTokenExchangeError, match="unavailable"):
            exchange_authorization_code(AUTH_CODE)


def test_tokens_are_not_written_to_application_logs() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "access_token": "log-me-not-access",
        "refresh_token": "log-me-not-refresh",
        "token_type": "bearer",
        "expires_in": 60,
    }
    with patch("app.services.amazon.lwa_token_service.httpx.Client", return_value=_mock_httpx_client(response)):
        with patch("app.services.amazon.lwa_token_service.logger.warning") as log_warning:
            exchange_authorization_code(AUTH_CODE)
    logged = str(log_warning.call_args_list)
    assert AUTH_CODE not in logged
    assert "log-me-not-access" not in logged
    assert "log-me-not-refresh" not in logged
    assert CLIENT_SECRET not in logged


def test_response_missing_refresh_token_raises() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"access_token": "only-access", "expires_in": 1}
    with patch("app.services.amazon.lwa_token_service.httpx.Client", return_value=_mock_httpx_client(response)):
        with pytest.raises(LwaTokenExchangeError, match="incomplete"):
            exchange_authorization_code(AUTH_CODE)
