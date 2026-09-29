from __future__ import annotations

"""
Amazon SP-API website authorization URI (Seller Central consent page).

Per Amazon's website authorization workflow:
1. Seller Central (or Vendor Central) base URL for the seller's store/region
2. Path: /apps/authorize/consent
3. Query: application_id={app id}, state={csrf token}
4. Optional: version=beta when the app is still in Draft (omit for published apps)

See: https://developer-docs.amazon.com/sp-api/docs/website-authorization-workflow
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AmazonOAuthState, User
from app.services.amazon.oauth_state import generate_internal_oauth_state, oauth_state_expires_at

AUTHORIZE_CONSENT_PATH = "/apps/authorize/consent"

# Region-specific Seller Central host per marketplace (must match the selling partner's store).
MARKETPLACE_SELLER_CENTRAL_BASE: dict[str, str] = {
    "A21TJRUUN4KGV": "https://sellercentral.amazon.in",  # Amazon.in (India)
}

def oauth_state_ttl() -> timedelta:
    return timedelta(minutes=settings.amazon_oauth_state_ttl_minutes)


class AmazonOAuthNotConfiguredError(Exception):
    """Raised when required Amazon SP-API authorization settings are missing."""


class UnsupportedMarketplaceError(Exception):
    """Raised when marketplace_id is not mapped to a Seller Central endpoint."""


def _require_amazon_connect_config() -> None:
    missing: list[str] = []
    if not settings.amazon_app_id:
        missing.append("AMAZON_APP_ID")
    if not settings.amazon_redirect_uri:
        missing.append("AMAZON_REDIRECT_URI")
    if missing:
        raise AmazonOAuthNotConfiguredError(", ".join(missing))


def seller_central_authorize_base(marketplace_id: str) -> str:
    base = MARKETPLACE_SELLER_CENTRAL_BASE.get(marketplace_id)
    if base:
        return base.rstrip("/")
    fallback = (settings.amazon_default_seller_central_url or "").strip().rstrip("/")
    if fallback:
        return fallback
    raise UnsupportedMarketplaceError(marketplace_id)


def build_authorization_url(marketplace_id: str, state: str) -> str:
    """Build Seller Central consent URL: {store}/apps/authorize/consent?application_id&state[&version=beta]."""
    _require_amazon_connect_config()
    store_base = seller_central_authorize_base(marketplace_id)
    params: dict[str, str] = {
        "application_id": settings.amazon_app_id or "",
        "state": state,
    }
    version = (settings.amazon_authorize_version or "").strip()
    if version:
        params["version"] = version
    return f"{store_base}{AUTHORIZE_CONSENT_PATH}?{urlencode(params)}"


def create_oauth_state_record(
    db: Session,
    *,
    user: User,
    marketplace_id: str,
) -> AmazonOAuthState:
    _require_amazon_connect_config()
    seller_central_authorize_base(marketplace_id)

    now = datetime.now(UTC)
    state_value = generate_internal_oauth_state()
    record = AmazonOAuthState(
        state=state_value,
        user_id=user.id,
        marketplace_id=marketplace_id,
        expires_at=oauth_state_expires_at(now),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def start_amazon_connect(db: Session, user: User, marketplace_id: str) -> str:
    try:
        record = create_oauth_state_record(db, user=user, marketplace_id=marketplace_id)
        return build_authorization_url(marketplace_id, record.state)
    except AmazonOAuthNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Amazon SP-API authorization is not configured on the server. "
                f"Missing environment variable(s): {exc.args[0]}."
            ),
        ) from exc
    except UnsupportedMarketplaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported marketplace_id: {exc.args[0]}",
        ) from exc
