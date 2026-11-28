"""Pick an SP-API marketplace the seller is registered in."""

from __future__ import annotations

from app.config import settings
from app.services.amazon.marketplace_participations import list_seller_marketplace_ids


def normalize_marketplace_for_seller(
    access_token: str,
    marketplace_id: str | None,
    *,
    default: str | None = None,
) -> str:
    """
    Return a marketplace ID this seller can use. Honors `marketplace_id` when the
    seller participates in that marketplace; otherwise uses default if listed, else
    the first participation.
    """
    fallback = (default or settings.amazon_default_marketplace_id or "").strip()
    requested = (marketplace_id or "").strip()
    if requested.lower() == "all":
        requested = ""

    participations = list_seller_marketplace_ids(access_token)
    if not participations:
        return requested or fallback

    if requested and requested in participations:
        return requested

    if fallback and fallback in participations:
        return fallback

    return participations[0]