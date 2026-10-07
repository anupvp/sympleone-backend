"""Signed HTTP client for Amazon Selling Partner API."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from app.config import settings
from app.services.amazon.amazon_credentials import sp_api_iam_signing_configured

logger = logging.getLogger(__name__)

SP_API_TIMEOUT_SECONDS = 45.0
USER_AGENT = "SympleOne/1.0 (Language=Python)"
_iam_signing_hint_logged = False


class SpApiConfigurationError(Exception):
    """SP-API AWS signing credentials are missing."""


class SpApiRequestError(Exception):
    """SP-API returned an error or could not be reached."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_sp_api_error(body: str) -> str | None:
    try:
        data = json.loads(body)
    except ValueError:
        return body[:240] if body else None
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        parts: list[str] = []
        for err in errors[:3]:
            if isinstance(err, dict):
                code = err.get("code") or err.get("Code")
                msg = err.get("message") or err.get("Message")
                if code and msg:
                    parts.append(f"{code}: {msg}")
                elif msg:
                    parts.append(str(msg))
        if parts:
            return "; ".join(parts)
    return body[:240] if body else None


def _sign_headers(method: str, url: str, headers: dict[str, str], host: str) -> dict[str, str]:
    access_key = (settings.amazon_sp_api_aws_access_key_id or "").strip()
    secret_key = (settings.amazon_sp_api_aws_secret_access_key or "").strip()
    region = (settings.amazon_sp_api_aws_region or "eu-west-1").strip()

    if not access_key or not secret_key:
        # OAuth (CLIENT_ID / CLIENT_SECRET / LWA token) is enough for many SP-API calls.
        return headers

    headers = {**headers, "host": host}
    credentials = Credentials(access_key, secret_key)
    aws_request = AWSRequest(method=method, url=url, headers=headers)
    SigV4Auth(credentials, "execute-api", region).add_auth(aws_request)
    return dict(aws_request.headers)


def sp_api_get(
    *,
    host: str,
    path: str,
    query: dict[str, str],
    access_token: str,
) -> dict[str, Any]:
    """Perform a signed GET against the Selling Partner API."""
    query_string = urlencode(query)
    url = f"https://{host}{path}?{query_string}"
    headers = {
        "x-amz-access-token": access_token,
        "user-agent": USER_AGENT,
        "host": host,
    }
    signed = _sign_headers("GET", url, headers, host)

    try:
        with httpx.Client(timeout=SP_API_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=signed)
    except httpx.HTTPError as exc:
        logger.warning("SP-API request failed: %s", type(exc).__name__)
        raise SpApiRequestError("Amazon API is temporarily unavailable") from exc

    if response.status_code != 200:
        global _iam_signing_hint_logged
        if (
            response.status_code in (401, 403)
            and not sp_api_iam_signing_configured()
            and not _iam_signing_hint_logged
        ):
            _iam_signing_hint_logged = True
            logger.warning(
                "SP-API returned %s without IAM signing keys. Add IAM user keys as "
                "AMAZON_SP_API_AWS_ACCESS_KEY_ID + AMAZON_SP_API_AWS_SECRET_ACCESS_KEY "
                "(or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) from Developer Central.",
                response.status_code,
            )
        detail = _extract_sp_api_error(response.text)
        logger.warning(
            "SP-API GET %s failed status=%s body=%s",
            path,
            response.status_code,
            response.text[:500],
        )
        message = detail or f"Amazon API request failed (HTTP {response.status_code})"
        raise SpApiRequestError(message, status_code=response.status_code)

    try:
        data = response.json()
    except ValueError as exc:
        raise SpApiRequestError("Amazon sales data response was invalid") from exc

    if not isinstance(data, dict):
        raise SpApiRequestError("Amazon sales data response was invalid")
    return data
