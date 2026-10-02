"""Amazon OAuth browser redirect URLs (frontend callback + success pages)."""

from urllib.parse import urlencode

from app.config import settings


def frontend_oauth_callback_url() -> str:
    """
    Public URL where Amazon redirects after seller consent (Symple One UI).

    Must match AMAZON_REDIRECT_URI in Seller Central / LWA.
    """
    explicit = (settings.amazon_oauth_frontend_callback_url or "").strip().rstrip("/")
    if explicit:
        return explicit

    redirect = (settings.amazon_redirect_uri or "").strip().rstrip("/")
    if redirect and "/amazon/callback" in redirect and "/api/amazon/callback" not in redirect:
        return redirect

    success = (settings.amazon_oauth_success_redirect_url or "").strip().rstrip("/")
    if success.endswith("/amazon/connect"):
        return f"{success[: -len('/amazon/connect')]}/amazon/callback"
    if success and success not in ("http://localhost:5173", "https://sympleone.onrender.com"):
        return f"{success}/amazon/callback"
    if success in ("https://sympleone.onrender.com", "http://localhost:5173"):
        return f"{success}/amazon/callback"

    return "http://localhost:5173/amazon/callback"


def build_frontend_callback_handoff_url(
    *,
    spapi_oauth_code: str,
    state: str,
    selling_partner_id: str,
) -> str:
    """Send the browser to the SPA callback route with Amazon query parameters."""
    query = urlencode(
        {
            "spapi_oauth_code": spapi_oauth_code,
            "state": state,
            "selling_partner_id": selling_partner_id,
        }
    )
    return f"{frontend_oauth_callback_url()}?{query}"
