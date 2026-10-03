"""SP-API regional endpoints per marketplace."""

from __future__ import annotations

# EU marketplaces (including Amazon.in A21TJRUUN4KGV).
_EU_MARKETPLACE_IDS = frozenset(
    {
        "A21TJRUUN4KGV",  # India
        "A1PA6795UKMFR9",  # Germany
        "A1RKKUPIHCS9HS",  # Spain
        "A13V1IB3VIYZZH",  # France
        "APJ6JRA9NG5V4",  # Italy
        "A1F83G8C2ARO7P",  # UK
        "AMEN7PMS3EDWL",  # Belgium
        "A1805IZSGTT6HS",  # Netherlands
        "A2NODRKZP88ZB9",  # Sweden
        "A1C3SOZRARQ6R3",  # Poland
        "ARBP9OOSHTCHU",  # Egypt
        "AE08WJ6YKNB5O",  # South Africa
        "A33AVAJ2PDY3EV",  # Turkey
        "A17E79C6D8DWNP",  # Saudi Arabia
        "A2VIGQ35RCS4UG",  # UAE
    }
)

_NA_MARKETPLACE_IDS = frozenset(
    {
        "ATVPDKIKX0DER",  # US
        "A2EUQ1WTGCTBG2",  # Canada
        "A1AM78C64UM0Y8",  # Mexico
        "A2Q3Y263D00KWC",  # Brazil
    }
)

_FE_MARKETPLACE_IDS = frozenset(
    {
        "A1VC38T7YXB528",  # Japan
        "A39IBJ37TRP1C6",  # Australia
        "A19VAU5U5O7RUS",  # Singapore
    }
)


def sp_api_host_for_marketplace(marketplace_id: str) -> str:
    mid = marketplace_id.strip().upper()
    if mid in _EU_MARKETPLACE_IDS:
        return "sellingpartnerapi-eu.amazon.com"
    if mid in _NA_MARKETPLACE_IDS:
        return "sellingpartnerapi-na.amazon.com"
    if mid in _FE_MARKETPLACE_IDS:
        return "sellingpartnerapi-fe.amazon.com"
    return "sellingpartnerapi-eu.amazon.com"
