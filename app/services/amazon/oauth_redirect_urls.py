"""Amazon OAuth browser redirect URLs (frontend callback + success pages)."""

from urllib.parse import urlencode, urlparse

from app.config import settings

_CONNECT_PATH = "/amazon/connect"
_CALLBACK_PATH = "/amazon/callback"
#_PRODUCTION_ORIGIN = "https://amazon.globalitstaffing.com"
_PRODUCTION_ORIGIN = "https://sympleone.onrender.com"
_PRODUCTION_CONNECT = f"{_PRODUCTION_ORIGIN}/amazon/amazon/connect"
_PRODUCTION_CALLBACK = f"{_PRODUCTION_ORIGIN}/amazon/amazon/callback"


def _use_production_site(url: str) -> str:
    """The old Render frontend is no longer the public site."""
    if "sympleone.onrender.com" not in url:
        return url
    stripped = url.rstrip("/")
    if stripped.endswith(_CALLBACK_PATH):
        return _PRODUCTION_CALLBACK
    return _PRODUCTION_CONNECT


def frontend_oauth_connect_url() -> str:
    """
    SPA route that shows success/error after OAuth (must include /amazon/connect).
    """
    explicit = (settings.amazon_oauth_success_redirect_url or "").strip().rstrip("/")
    if explicit.endswith(_CONNECT_PATH):
        return _use_production_site(explicit)

    redirect = (settings.amazon_redirect_uri or "").strip().rstrip("/")
    if (
        redirect.endswith(_CALLBACK_PATH)
        and "/api/amazon/callback" not in redirect
    ):
        return _use_production_site(f"{redirect[: -len(_CALLBACK_PATH)]}{_CONNECT_PATH}")

    if explicit:
        parsed = urlparse(explicit if "://" in explicit else f"https://{explicit}")
        if parsed.path in ("", "/"):
            return _use_production_site(f"{parsed.scheme}://{parsed.netloc}{_CONNECT_PATH}")
        built = explicit if explicit.endswith(_CONNECT_PATH) else f"{explicit}{_CONNECT_PATH}"
        return _use_production_site(built)

    return f"http://localhost:5173{_CONNECT_PATH}"


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
        return _use_production_site(redirect)

    connect = frontend_oauth_connect_url()
    if connect.endswith(_CONNECT_PATH):
        return f"{connect[: -len(_CONNECT_PATH)]}{_CALLBACK_PATH}"
    return f"{connect}{_CALLBACK_PATH}"


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
