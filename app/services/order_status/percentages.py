"""Integer percentages that sum to 100 for dashboard display."""

from __future__ import annotations

from app.models.dashboard_orders import NormalizedOrderStatus

STATUS_COLORS = {
    NormalizedOrderStatus.DELIVERED: "#22C55E",
    NormalizedOrderStatus.IN_TRANSIT: "#3B82F6",
    NormalizedOrderStatus.PROCESSING: "#F59E0B",
    NormalizedOrderStatus.CANCELLED: "#EF4444",
}

STATUS_LABELS = {
    NormalizedOrderStatus.DELIVERED: "Delivered",
    NormalizedOrderStatus.IN_TRANSIT: "In Transit",
    NormalizedOrderStatus.PROCESSING: "Processing",
    NormalizedOrderStatus.CANCELLED: "Cancelled",
}

_STATUS_ORDER = [
    NormalizedOrderStatus.DELIVERED,
    NormalizedOrderStatus.IN_TRANSIT,
    NormalizedOrderStatus.PROCESSING,
    NormalizedOrderStatus.CANCELLED,
]


def integer_percentages(counts: dict[NormalizedOrderStatus, int], total: int) -> dict[NormalizedOrderStatus, int]:
    if total <= 0:
        return {status: 0 for status in _STATUS_ORDER}

    raw = {status: (counts.get(status, 0) / total) * 100.0 for status in _STATUS_ORDER}
    floors = {status: int(raw[status]) for status in _STATUS_ORDER}
    remainder = 100 - sum(floors.values())
    if remainder <= 0:
        return floors

    fractions = sorted(
        _STATUS_ORDER,
        key=lambda s: (raw[s] - floors[s], counts.get(s, 0)),
        reverse=True,
    )
    result = dict(floors)
    idx = 0
    while remainder > 0 and fractions:
        status = fractions[idx % len(fractions)]
        result[status] += 1
        remainder -= 1
        idx += 1
    return result