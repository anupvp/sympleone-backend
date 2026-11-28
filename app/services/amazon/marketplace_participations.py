"""Seller marketplace participations (Sellers API)."""

from __future__ import annotations

import logging
from typing import Any

from app.services.amazon.sp_api_client import SpApiRequestError, sp_api_get

logger = logging.getLogger(__name__)

MARKETPLACE_PARTICIPATIONS_PATH = "/sellers/v1/marketplaceParticipations"

_SP_API_HOSTS = (
    "sellingpartnerapi-eu.amazon.com",
    "sellingpartnerapi-na.amazon.com",
    "sellingpartnerapi-fe.amazon.com",
)


def _parse_participation_ids(data: dict[str, Any]) -> list[str]:
    payload = data.get("payload")
    if not isinstance(payload, list):
        return []
    ids: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        marketplace = row.get("marketplace")
        if not isinstance(marketplace, dict):
            continue
        mp_id = marketplace.get("id")
        if isinstance(mp_id, str) and mp_id.strip():
            participation = row.get("participation")
            if isinstance(participation, dict) and participation.get("isParticipating") is False:
                continue
            ids.append(mp_id.strip())
    return ids


def fetch_marketplace_participation_ids(
    *,
    access_token: str,
    host: str,
) -> list[str]:
    data = sp_api_get(
        host=host,
        path=MARKETPLACE_PARTICIPATIONS_PATH,
        query=None,
        access_token=access_token,
    )
    return _parse_participation_ids(data)


def list_seller_marketplace_ids(access_token: str) -> list[str]:
    """Try each SP-API region until participations are returned."""
    last_error: SpApiRequestError | None = None
    for host in _SP_API_HOSTS:
        try:
            ids = fetch_marketplace_participation_ids(access_token=access_token, host=host)
        except SpApiRequestError as exc:
            last_error = exc
            continue
        if ids:
            return ids
    if last_error is not None:
        logger.debug("Marketplace participations unavailable: %s", last_error)
    return []