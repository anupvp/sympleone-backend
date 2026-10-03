"""Signed HTTP client for Amazon Selling Partner API."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from app.config import settings

logger = logging.getLogger(__name__)

SP_API_TIMEOUT_SECONDS = 45.0
USER_AGENT = "SympleOne/1.0 (Language=Python)"


class SpApiConfigurationError(Exception):
    """SP-API AWS signing credentials are missing."""


class SpApiRequestError(Exception):
    """SP-API returned an error or could not be reached."""


def _sign_headers(method: str, url: str, headers: dict[str, str], host: str) -> dict[str, str]:
    access_key = (settings.amazon_sp_api_aws_access_key_id or "").strip()
    secret_key = (settings.amazon_sp_api_aws_secret_access_key or "").strip()
    region = (settings.amazon_sp_api_aws_region or "eu-west-1").strip()

    if not access_key or not secret_key:
        logger.warning(
            "AMAZON_SP_API_AWS_ACCESS_KEY_ID / AMAZON_SP_API_AWS_SECRET_ACCESS_KEY not set; "
            "SP-API request may be rejected by Amazon"
        )
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
        raise SpApiRequestError("Amazon sales data is temporarily unavailable") from exc

    if response.status_code != 200:
        logger.warning(
            "SP-API GET %s failed status=%s body=%s",
            path,
            response.status_code,
            response.text[:500],
        )
        raise SpApiRequestError("Amazon sales data could not be loaded")

    try:
        data = response.json()
    except ValueError as exc:
        raise SpApiRequestError("Amazon sales data response was invalid") from exc

    if not isinstance(data, dict):
        raise SpApiRequestError("Amazon sales data response was invalid")
    return data
