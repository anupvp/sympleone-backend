from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AmazonAppstoreOAuthSession, User
from app.services.amazon.oauth_state import generate_internal_oauth_state, oauth_state_expires_at

logger = logging.getLogger(__name__)

_SELLING_PARTNER_ID = re.compile(r"^[A-Z0-9]{5,32}$")

# Amazon Appstore returns callback URIs on Amazon-operated hosts (Seller/Vendor Central, amazon.*).
_AMAZON_CALLBACK_HOST = re.compile(
    r"^([a-z0-9-]+\.)*amazon\.(com|in|co\.uk|de|fr|es|it|nl|se|pl|com\.br|com\.mx|co\.jp|ae|sa|sg|com\.au|ca)$",
    re.IGNORECASE,
)

_BLOCKED_SCHEMES = frozenset({"javascript", "data", "file", "vbscript"})


class AppstoreLoginValidationError(ValueError):
    """Invalid Appstore login query parameters."""


class AppstoreLoginConfigurationError(RuntimeError):
    """Amazon Appstore login is not configured (missing or invalid server settings)."""


def validate_selling_partner_id(selling_partner_id: str) -> None:
    if not selling_partner_id:
        raise AppstoreLoginValidationError("Invalid selling_partner_id")
    if not _SELLING_PARTNER_ID.match(selling_partner_id.strip()):
        raise AppstoreLoginValidationError("Invalid selling_partner_id")


def validate_amazon_callback_uri(amazon_callback_uri: str) -> None:
    if not amazon_callback_uri:
        raise AppstoreLoginValidationError("Invalid amazon_callback_uri")
    parsed = urlparse(amazon_callback_uri)
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise AppstoreLoginValidationError("Invalid amazon_callback_uri scheme")
    if parsed.scheme.lower() != "https":
        raise AppstoreLoginValidationError("amazon_callback_uri must use HTTPS")
    host = parsed.hostname
    if not host:
        raise AppstoreLoginValidationError("Invalid amazon_callback_uri host")
    if host.lower() in ("localhost", "127.0.0.1") or host.endswith(".local"):
        raise AppstoreLoginValidationError("amazon_callback_uri host not allowed")
    if not _AMAZON_CALLBACK_HOST.match(host.lower()):
        raise AppstoreLoginValidationError("amazon_callback_uri host is not an Amazon endpoint")


def symple_oauth_redirect_uri() -> str:
    """Symple One SP-API OAuth callback URL (sent to Amazon as redirect_uri)."""
    raw = settings.amazon_redirect_uri
    if not raw or not raw.strip():
        raise AppstoreLoginConfigurationError("AMAZON_REDIRECT_URI is not configured")
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        raise AppstoreLoginConfigurationError("AMAZON_REDIRECT_URI must use HTTPS")
    if not parsed.netloc:
        raise AppstoreLoginConfigurationError("AMAZON_REDIRECT_URI is invalid")
    return value


def validate_amazon_state(amazon_state: str) -> None:
    """Validate without modifying amazon_state (must be stored and redirected exactly)."""
    if amazon_state == "":
        raise AppstoreLoginValidationError("Invalid amazon_state")
    if len(amazon_state) > 512:
        raise AppstoreLoginValidationError("Invalid amazon_state")


def build_appstore_return_redirect_url(
    amazon_callback_uri: str,
    *,
    amazon_state: str,
    internal_state: str,
    symple_redirect_uri: str,
) -> str:
    """
    Build Amazon Appstore return URL via urllib.parse (no manual string concatenation).

    Uses the amazon_callback_uri from Amazon, preserves amazon_state, sets Symple One
    ``redirect_uri``, and adds internal_state as query parameter ``state``.
    """
    parsed = urlparse(amazon_callback_uri)
    if parsed.scheme.lower() != "https":
        raise AppstoreLoginValidationError("amazon_callback_uri must use HTTPS")

    existing = parse_qsl(parsed.query, keep_blank_values=True)
    merged: dict[str, str] = dict(existing)
    merged["amazon_state"] = amazon_state
    merged["state"] = internal_state
    merged["redirect_uri"] = symple_redirect_uri
    new_query = urlencode(merged)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def create_appstore_oauth_session(
    db: Session,
    *,
    amazon_callback_uri: str,
    amazon_state: str,
    selling_partner_id: str,
    user: User | None,
    organization_id: str | None = None,
) -> AmazonAppstoreOAuthSession:
    now = datetime.now(UTC)
    # Symple One CSRF token (never reuse or derive from Amazon's amazon_state).
    symple_state = generate_internal_oauth_state()
    session = AmazonAppstoreOAuthSession(
        internal_state=symple_state,
        amazon_state=amazon_state,
        selling_partner_id=selling_partner_id,
        amazon_callback_uri=amazon_callback_uri,
        user_id=user.id if user else None,
        organization_id=organization_id,
        expires_at=oauth_state_expires_at(now),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def process_appstore_login(
    db: Session,
    *,
    amazon_callback_uri: str,
    amazon_state: str,
    selling_partner_id: str,
    user: User | None,
) -> str:
    validate_amazon_callback_uri(amazon_callback_uri)
    validate_amazon_state(amazon_state)
    validate_selling_partner_id(selling_partner_id)

    logger.info(
        "Amazon Appstore OAuth login initiated for selling_partner_id=%s",
        selling_partner_id.strip(),
    )

    symple_redirect = symple_oauth_redirect_uri()

    record = create_appstore_oauth_session(
        db,
        amazon_callback_uri=amazon_callback_uri,
        amazon_state=amazon_state,
        selling_partner_id=selling_partner_id,
        user=user,
    )

    return build_appstore_return_redirect_url(
        amazon_callback_uri,
        amazon_state=amazon_state,
        internal_state=record.internal_state,
        symple_redirect_uri=symple_redirect,
    )
