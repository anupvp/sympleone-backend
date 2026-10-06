"""Account health metrics for the dashboard card (placeholder until SP-API wiring)."""

from __future__ import annotations

from app.models import User


def _metric(metric_id: str, label: str, score: float) -> dict:
    """score 0–100: higher means more risk / worse health."""
    if score >= 70:
        status = "critical"
    elif score >= 40:
        status = "warning"
    else:
        status = "good"
    return {
        "id": metric_id,
        "label": label,
        "score": round(max(0.0, min(100.0, score)), 1),
        "status": status,
    }


def build_account_health_for_user(_db, _user: User) -> dict:
    metrics = [
        _metric("policyViolation", "Policy Violation", 18.0),
        _metric("orderCancellationRate", "Order Cancellation Rate", 6.5),
        _metric("paymentHold", "Payment Hold", 42.0),
        _metric("lowInventory", "Low Inventory", 58.0),
        _metric("adsBudgetExhausted", "Ads Budget Exhausted", 24.0),
        _metric("orderDefectRate", "Order Defect Rate", 11.0),
    ]
    return {"metrics": metrics}
