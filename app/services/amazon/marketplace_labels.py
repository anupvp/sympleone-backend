from __future__ import annotations

_LABELS: dict[str, str] = {
    "A21TJRUUN4KGV": "Amazon.in",
    "ATVPDKIKX0DER": "Amazon.com",
    "A1F83G8C2ARO7P": "Amazon.co.uk",
    "A1PA6795UKMFR9": "Amazon.de",
    "A2EUQ1WTGCTBG2": "Amazon.ca",
    "A1VC38T7YXB528": "Amazon.co.jp",
}


def marketplace_label(marketplace_id: str) -> str:
    mid = marketplace_id.strip().upper()
    return _LABELS.get(mid, "Amazon")