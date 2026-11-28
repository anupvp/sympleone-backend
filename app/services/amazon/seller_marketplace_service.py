from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.marketplace_labels import marketplace_label
from app.services.amazon.listings_marketplace_probe import resolve_listings_marketplace_id
from app.services.amazon.marketplace_participations import list_seller_marketplace_ids
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError


class SellerMarketplaceError(Exception):
    pass


def get_seller_marketplace_context(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise SellerMarketplaceError("Marketplace context is only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise SellerMarketplaceError("Connect your Amazon seller account first")

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise SellerMarketplaceError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    participations = list_seller_marketplace_ids(access_token)
    try:
        resolved = resolve_listings_marketplace_id(
            access_token,
            selling_partner_id=connection.selling_partner_id,
            marketplace_id=marketplace_id,
        )
    except SpApiRequestError as exc:
        raise SellerMarketplaceError(str(exc)) from exc
    return {
        "selling_partner_id": connection.selling_partner_id,
        "marketplace_id": resolved,
        "marketplace_label": marketplace_label(resolved),
        "participating_marketplace_ids": participations,
    }