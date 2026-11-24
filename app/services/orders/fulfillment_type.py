"""Classify Amazon orders into FBA, FBM, or Self Ship (Easy Ship)."""

from __future__ import annotations

from typing import Any

FULFILLMENT_FBA = "FBA"
FULFILLMENT_FBM = "FBM"
FULFILLMENT_SELF_SHIP = "SELF_SHIP"

_LABELS = {
    FULFILLMENT_FBA: "FBA",
    FULFILLMENT_FBM: "FBM",
    FULFILLMENT_SELF_SHIP: "Self Ship",
}


def classify_fulfillment_type(raw: dict[str, Any]) -> str:
    """Map Amazon orders to FBA, FBM (MFN), or Self Ship (Easy Ship only).

    Self Ship is exclusively Amazon Easy Ship: never FBA (AFN), and never plain
  merchant FBM/MFN without Easy Ship signals.
    """
    channel = str(raw.get("FulfillmentChannel") or "").strip().upper()
    easy_raw = raw.get("EasyShipShipmentStatus")
    easy_ship = isinstance(easy_raw, str) and bool(easy_raw.strip())

    service_level = str(raw.get("ShipmentServiceLevelCategory") or "").strip().upper()
    is_easy_service = "EASY" in service_level or service_level == "EASYSHIP"
    is_easy = easy_ship or is_easy_service

    if channel == "AFN":
        return FULFILLMENT_FBA

    if is_easy:
        return FULFILLMENT_SELF_SHIP

    return FULFILLMENT_FBM


def fulfillment_label(fulfillment_type: str) -> str:
    return _LABELS.get(fulfillment_type, fulfillment_type)


def summarize_fulfillment_types(orders: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(orders),
        "fba": 0,
        "fbm": 0,
        "self_ship": 0,
    }
    for row in orders:
        ftype = row.get("fulfillment_type")
        if ftype == FULFILLMENT_FBA:
            summary["fba"] += 1
        elif ftype == FULFILLMENT_SELF_SHIP:
            summary["self_ship"] += 1
        else:
            summary["fbm"] += 1
    return summary