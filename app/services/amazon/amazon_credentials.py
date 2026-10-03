"""Resolve Amazon OAuth vs SP-API IAM signing configuration."""

from __future__ import annotations

from app.config import settings


def amazon_oauth_configured() -> bool:
    return bool(
        (settings.amazon_client_id or "").strip()
        and (settings.amazon_client_secret or "").strip()
        and (settings.amazon_redirect_uri or "").strip()
    )


def sp_api_iam_signing_configured() -> bool:
    return bool(
        (settings.amazon_sp_api_aws_access_key_id or "").strip()
        and (settings.amazon_sp_api_aws_secret_access_key or "").strip()
    )
