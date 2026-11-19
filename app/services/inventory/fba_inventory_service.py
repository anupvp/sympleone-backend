"""FBA inventory summaries for the inventory UI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import User, UserKind
from app.services.amazon.fba_inventory_summaries import (
    fetch_inventory_summaries_paginated,
    normalize_inventory_item,
    summarize_inventory_metrics,
)
from app.services.amazon.lwa_token_service import LwaTokenExchangeError, refresh_lwa_access_token
from app.services.amazon.seller_connection_service import find_active_connection_for_user
from app.services.amazon.sp_api_client import SpApiRequestError


class FbaInventoryError(Exception):
    """FBA inventory could not be loaded."""


def build_fba_inventory_for_user(
    db: Session,
    user: User,
    *,
    marketplace_id: str | None,
    seller: User | None = None,
) -> dict:
    subject = seller if seller is not None else user
    if subject.kind != UserKind.SELLER:
        raise FbaInventoryError("FBA inventory is only available for seller accounts")

    connection = find_active_connection_for_user(db, subject.id)
    if connection is None:
        raise FbaInventoryError(
            "Connect your Amazon seller account before viewing FBA inventory"
        )

    marketplace = (marketplace_id or "").strip()
    if not marketplace or marketplace.lower() == "all":
        marketplace = settings.amazon_default_marketplace_id

    try:
        refresh_token = decrypt_secret(connection.refresh_token_ciphertext)
        access_token = refresh_lwa_access_token(refresh_token)
    except LwaTokenExchangeError as exc:
        raise FbaInventoryError(
            "Amazon authorization expired; reconnect your seller account"
        ) from exc

    try:
        summaries, truncated = fetch_inventory_summaries_paginated(
            access_token=access_token,
            marketplace_id=marketplace,
            start=None,
        )
    except SpApiRequestError as exc:
        raise FbaInventoryError(str(exc)) from exc

    metrics = summarize_inventory_metrics(summaries)
    items = [normalize_inventory_item(row) for row in summaries]
    items.sort(
        key=lambda row: (
            -(row.get("fulfillable") or 0),
            str(row.get("sellerSku") or ""),
        ),
    )

    granularity_type = "Marketplace"
    return {
        "marketplaceId": marketplace,
        "granularityType": granularity_type,
        "truncated": truncated,
        "isEmpty": len(summaries) == 0,
        "metrics": metrics,
        "items": items,
    }