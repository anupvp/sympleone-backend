from app.config import settings
from app.services.amazon.oauth_redirect_urls import (
    frontend_oauth_callback_url,
    frontend_oauth_connect_url,
)


def test_connect_url_derived_from_frontend_redirect_uri() -> None:
    settings.amazon_redirect_uri = "https://sympleone.onrender.com/amazon/callback"
    settings.amazon_oauth_success_redirect_url = "https://sympleone.onrender.com"
    assert frontend_oauth_connect_url() == "https://sympleone.onrender.com/amazon/connect"
    assert frontend_oauth_callback_url() == "https://sympleone.onrender.com/amazon/callback"
