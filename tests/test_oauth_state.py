from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.config import settings
from app.services.amazon.oauth_state import generate_internal_oauth_state, oauth_state_expires_at


def test_generate_internal_oauth_state_uses_token_urlsafe_32() -> None:
    with patch("app.services.amazon.oauth_state.secrets.token_urlsafe") as mock_token:
        mock_token.return_value = "fixed-state"
        assert generate_internal_oauth_state() == "fixed-state"
        mock_token.assert_called_once_with(32)


def test_oauth_state_expires_at_respects_configurable_ttl() -> None:
    settings.amazon_oauth_state_ttl_minutes = 15
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    expires = oauth_state_expires_at(now)
    assert expires == now + timedelta(minutes=15)
