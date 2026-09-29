"""Shared OAuth state generation and TTL for Amazon authorization flows."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from app.config import settings


def generate_internal_oauth_state() -> str:
    """Cryptographically secure CSRF token for Amazon OAuth (URL-safe, 32 bytes entropy)."""
    return secrets.token_urlsafe(32)


def oauth_state_expires_at(now: datetime | None = None) -> datetime:
    """Expiry timestamp for a new OAuth state/session record."""
    base = now or datetime.now(UTC)
    return base + timedelta(minutes=settings.amazon_oauth_state_ttl_minutes)
