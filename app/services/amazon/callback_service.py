from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AmazonAppstoreOAuthSession
from app.services.amazon.seller_connection_service import upsert_seller_connection
from app.services.amazon.appstore_login_service import (
    AppstoreLoginValidationError,
    validate_selling_partner_id,
)
from app.services.amazon.lwa_token_service import (
    LwaConfigurationError,
    LwaTokenExchangeError,
    exchange_authorization_code,
)

logger = logging.getLogger(__name__)


class CallbackValidationError(ValueError):
    """Invalid OAuth callback parameters or session state."""


class CallbackProcessingError(Exception):
    """Callback could not be completed (e.g. LWA or persistence)."""


def _secure_str_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _success_redirect_url() -> str:
    base = (settings.amazon_oauth_success_redirect_url or "").strip()
    if not base:
        base = "http://localhost:5173/dashboard"
    return _append_query(base, {"amazon": "connected"})


def error_redirect_url() -> str:
    base = (settings.amazon_oauth_success_redirect_url or "").strip()
    if not base:
        base = "http://localhost:5173/dashboard"
    return _append_query(base, {"amazon": "error"})


def _append_query(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    merged = dict(parse_qsl(parsed.query, keep_blank_values=True))
    merged.update(params)
    query = urlencode(merged)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def _load_oauth_session(db: Session, internal_state: str) -> AmazonAppstoreOAuthSession:
    row = db.execute(
        select(AmazonAppstoreOAuthSession).where(
            AmazonAppstoreOAuthSession.internal_state == internal_state
        )
    ).scalar_one_or_none()
    if not row:
        raise CallbackValidationError("Invalid or unknown OAuth state")
    return row


def _assert_session_valid(
    session: AmazonAppstoreOAuthSession,
    selling_partner_id: str,
) -> None:
    if session.used_at is not None:
        raise CallbackValidationError("OAuth state has already been used")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise CallbackValidationError("OAuth state has expired")
    if not _secure_str_equal(session.selling_partner_id, selling_partner_id):
        raise CallbackValidationError("selling_partner_id does not match OAuth session")


def process_amazon_oauth_callback(
    db: Session,
    *,
    spapi_oauth_code: str,
    state: str,
    selling_partner_id: str,
) -> str:
    """
    Complete Appstore OAuth after Amazon redirects to Symple One.

    Trust only server-stored OAuth session fields (user_id, organization_id, seller id).
    """
    if spapi_oauth_code == "":
        raise CallbackValidationError("spapi_oauth_code is required")
    if state == "":
        raise CallbackValidationError("state is required")
    if selling_partner_id == "":
        raise CallbackValidationError("selling_partner_id is required")
    try:
        validate_selling_partner_id(selling_partner_id)
    except AppstoreLoginValidationError as exc:
        raise CallbackValidationError(str(exc)) from exc

    oauth_session = _load_oauth_session(db, state)
    _assert_session_valid(oauth_session, selling_partner_id)

    logger.info(
        "Amazon OAuth callback processing for selling_partner_id=%s",
        oauth_session.selling_partner_id.strip(),
    )

    try:
        token_payload = exchange_authorization_code(spapi_oauth_code)
    except LwaConfigurationError as exc:
        raise CallbackProcessingError(f"Amazon LWA is not configured: {exc.args[0]}") from exc
    except LwaTokenExchangeError as exc:
        raise CallbackProcessingError("Amazon authorization could not be completed") from exc

    refresh_token = token_payload["refresh_token"]
    upsert_seller_connection(db, oauth_session=oauth_session, refresh_token=refresh_token)
    oauth_session.used_at = datetime.now(UTC)
    db.commit()

    return _success_redirect_url()
