"""Discover which marketplace a seller's Listings API supports."""

from __future__ import annotations

from app.config import settings
from app.services.amazon.listings_items import probe_seller_listings_access
from app.services.amazon.marketplace_participations import list_seller_marketplace_ids
from app.services.amazon.sp_api_client import SpApiRequestError


def _is_marketplace_registration_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "not registered in marketplace" in msg or (
        "invalidinput" in msg and "marketplace" in msg
    )


def _candidate_marketplace_ids(
    *,
    participations: list[str],
    requested: str,
    default: str,
) -> list[str]:
    probe_order = (
        "ATVPDKIKX0DER",  # US
        "A1F83G8C2ARO7P",  # UK
        "A1PA6795UKMFR9",  # DE
        "A2EUQ1WTGCTBG2",  # CA
        "A1VC38T7YXB528",  # JP
        "A21TJRUUN4KGV",  # India
    )
    ordered: list[str] = []
    seen: set[str] = set()

    def add(mp: str | None) -> None:
        if not mp:
            return
        key = mp.strip().upper()
        if not key or key in seen:
            return
        seen.add(key)
        ordered.append(key)

    for mp in participations:
        add(mp)

    allow_requested = not requested or not participations or requested in participations
    if allow_requested:
        add(requested)

    for mp in probe_order:
        add(mp)
    add(default)
    if requested and not allow_requested:
        add(requested)
    return ordered


def resolve_listings_marketplace_id(
    access_token: str,
    *,
    selling_partner_id: str,
    marketplace_id: str | None,
) -> str:
    """
    Pick a marketplace where Listings Items works for this seller. Uses participations
    when available, otherwise probes common marketplaces (skipping invalid ones).
    """
    default = (settings.amazon_default_marketplace_id or "").strip()
    requested = (marketplace_id or "").strip()
    if requested.lower() == "all":
        requested = ""

    participations = list_seller_marketplace_ids(access_token)
    candidates = _candidate_marketplace_ids(
        participations=participations,
        requested=requested,
        default=default,
    )

    # Participations reported but request is wrong — try participation markets before India default.
    if participations and requested and requested not in participations:
        candidates = _candidate_marketplace_ids(
            participations=participations,
            requested="",
            default=default,
        )

    last_error: SpApiRequestError | None = None
    for mp in candidates:
        try:
            probe_seller_listings_access(
                access_token=access_token,
                selling_partner_id=selling_partner_id,
                marketplace_id=mp,
            )
            return mp
        except SpApiRequestError as exc:
            last_error = exc
            if _is_marketplace_registration_error(exc):
                continue
            raise

    if last_error is not None:
        raise last_error
    raise SpApiRequestError("Could not determine a marketplace for this seller")