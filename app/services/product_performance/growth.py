"""Growth calculations for product performance comparison periods."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GrowthResult:
    growth_percentage: float | None
    growth_display: str


def compute_growth(current_sales: float, previous_sales: float) -> GrowthResult:
    current = max(0.0, float(current_sales))
    previous = max(0.0, float(previous_sales))

    if previous <= 0 and current > 0:
        return GrowthResult(growth_percentage=None, growth_display="NEW")
    if previous <= 0 and current <= 0:
        return GrowthResult(growth_percentage=0.0, growth_display="0%")
    if previous > 0 and current <= 0:
        return GrowthResult(growth_percentage=-100.0, growth_display="-100%")

    pct = round(((current - previous) / previous) * 100, 1)
    sign = "+" if pct > 0 else ""
    return GrowthResult(
        growth_percentage=pct,
        growth_display=f"{sign}{pct:g}%",
    )


def growth_sort_key(result: GrowthResult) -> float:
    """Ascending sort for low performers; NEW products sort last."""
    if result.growth_display == "NEW":
        return float("inf")
    if result.growth_percentage is None:
        return float("inf")
    return result.growth_percentage