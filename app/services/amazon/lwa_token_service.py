from __future__ import annotations

import logging
from typing import Any, TypedDict
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

LWA_REQUEST_TIMEOUT_SECONDS = 30.0
LWA_TOKEN_CONTENT_TYPE = "application/x-www-form-urlencoded;charset=UTF-8"


class LwaConfigurationError(Exception):
    """Amazon LWA client credentials or redirect URI are not configured."""


class LwaTokenExchangeError(Exception):
    """Amazon Login with Amazon token exchange failed."""


class LwaTokenExchangeResult(TypedDict):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def _lwa_token_url() -> str:
    return (settings.amazon_lwa_token_url or "https://api.amazon.com/auth/o2/token").strip()


def _require_lwa_config() -> tuple[str, str, str]:
    client_id = (settings.amazon_client_id or "").strip()
    client_secret = (settings.amazon_client_secret or "").strip()
    redirect_uri = (settings.amazon_redirect_uri or "").strip()
    missing = []
    if not client_id:
        missing.append("AMAZON_CLIENT_ID")
    if not client_secret:
        missing.append("AMAZON_CLIENT_SECRET")
    if not redirect_uri:
        missing.append("AMAZON_REDIRECT_URI or AMAZON_LOGIN_URI")
    if missing:
        raise LwaConfigurationError(", ".join(missing))
    return client_id, client_secret, redirect_uri


def _normalize_token_response(data: dict[str, Any]) -> LwaTokenExchangeResult:
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    if not refresh_token or not access_token:
        raise LwaTokenExchangeError("token exchange incomplete")
    token_type = str(data.get("token_type") or "bearer")
    try:
        expires_in = int(data.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0
    return LwaTokenExchangeResult(
        access_token=str(access_token),
        refresh_token=str(refresh_token),
        token_type=token_type,
        expires_in=expires_in,
    )


def exchange_authorization_code(spapi_oauth_code: str) -> LwaTokenExchangeResult:
    """
    Exchange SP-API authorization code for LWA tokens (server-side only).

    POST https://api.amazon.com/auth/o2/token

    Body (form-urlencoded, UTF-8):
    grant_type=authorization_code&code=...&redirect_uri=...&client_id=...&client_secret=...
    """
    client_id, client_secret, redirect_uri = _require_lwa_config()
    form_fields = [
        ("grant_type", "authorization_code"),
        ("code", spapi_oauth_code),
        ("redirect_uri", redirect_uri),
        ("client_id", client_id),
        ("client_secret", client_secret),
    ]
    body = urlencode(form_fields)
    try:
        with httpx.Client(timeout=LWA_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(
                _lwa_token_url(),
                content=body.encode("utf-8"),
                headers={"Content-Type": LWA_TOKEN_CONTENT_TYPE},
            )
    except httpx.HTTPError as exc:
        logger.warning("Amazon LWA token exchange request failed: %s", type(exc).__name__)
        raise LwaTokenExchangeError("token exchange unavailable") from exc

    if response.status_code != 200:
        logger.warning(
            "Amazon LWA token exchange failed with status=%s",
            response.status_code,
        )
        raise LwaTokenExchangeError("token exchange rejected")

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Amazon LWA token exchange returned invalid JSON")
        raise LwaTokenExchangeError("token exchange incomplete") from exc

    if not isinstance(data, dict):
        raise LwaTokenExchangeError("token exchange incomplete")

    return _normalize_token_response(data)


def refresh_lwa_access_token(refresh_token: str) -> str:
    """
    Exchange a refresh token for a short-lived SP-API access token.

    POST https://api.amazon.com/auth/o2/token (grant_type=refresh_token)
    """
    client_id, client_secret, _redirect_uri = _require_lwa_config()
    form_fields = [
        ("grant_type", "refresh_token"),
        ("refresh_token", refresh_token),
        ("client_id", client_id),
        ("client_secret", client_secret),
    ]
    body = urlencode(form_fields)
    try:
        with httpx.Client(timeout=LWA_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(
                _lwa_token_url(),
                content=body.encode("utf-8"),
                headers={"Content-Type": LWA_TOKEN_CONTENT_TYPE},
            )
    except httpx.HTTPError as exc:
        logger.warning("Amazon LWA refresh request failed: %s", type(exc).__name__)
        raise LwaTokenExchangeError("token refresh unavailable") from exc

    if response.status_code != 200:
        logger.warning("Amazon LWA refresh failed with status=%s", response.status_code)
        raise LwaTokenExchangeError("token refresh rejected")

    try:
        data = response.json()
    except ValueError as exc:
        raise LwaTokenExchangeError("token refresh incomplete") from exc

    if not isinstance(data, dict):
        raise LwaTokenExchangeError("token refresh incomplete")

    access_token = data.get("access_token")
    if not access_token:
        raise LwaTokenExchangeError("token refresh incomplete")
    return str(access_token)
