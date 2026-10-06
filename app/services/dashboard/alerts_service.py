"""Operational alerts grouped by category for the header bell."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, UserKind
from app.services.seller_access_requests import list_pending_for_admin, pending_access_request_count


def _item(
    *,
    id: str,
    category: str,
    category_label: str,
    count: int,
    title: str,
    tone: str,
    href: str | None = None,
) -> dict:
    return {
        "id": id,
        "category": category,
        "categoryLabel": category_label,
        "count": count,
        "title": title,
        "tone": tone,
        "href": href,
    }


def build_dashboard_alerts(db: Session, user: User) -> list[dict]:
    items: list[dict] = []

    if user.kind == UserKind.ADMIN:
        pending = list_pending_for_admin(db)
        if pending:
            for req in pending[:5]:
                items.append(
                    _item(
                        id=f"access-{req['id']}",
                        category="directory",
                        category_label="Directory & access",
                        count=1,
                        title=f"{req['seller_name']}: access requested by {req['employee_name']}",
                        tone="blue",
                        href="/admin/sellers",
                    )
                )
            extra = len(pending) - 5
            if extra > 0:
                items.append(
                    _item(
                        id="access-more",
                        category="directory",
                        category_label="Directory & access",
                        count=extra,
                        title="More pending seller access requests",
                        tone="blue",
                        href="/admin/sellers",
                    )
                )

        items.extend(
            [
                _item(
                    id="seller-added",
                    category="directory",
                    category_label="Directory & access",
                    count=0,
                    title="Seller / user / group additions",
                    tone="green",
                    href="/admin/sellers",
                ),
                _item(
                    id="seller-removed",
                    category="directory",
                    category_label="Directory & access",
                    count=0,
                    title="Seller / user / group removals",
                    tone="amber",
                    href="/admin/employees",
                ),
            ]
        )

        items.extend(
            [
                _item(
                    id="seller-risk",
                    category="risk",
                    category_label="Account risk",
                    count=2,
                    title="Seller accounts under risk review",
                    tone="red",
                    href="/admin/sellers",
                ),
                _item(
                    id="account-health-issues",
                    category="account_health",
                    category_label="Account health",
                    count=3,
                    title="Account health issues",
                    tone="red",
                    href="/dashboard",
                ),
                _item(
                    id="policy-violation",
                    category="risk",
                    category_label="Account risk",
                    count=1,
                    title="Policy violations by sellers",
                    tone="red",
                    href="/admin/sellers",
                ),
                _item(
                    id="payment-hold",
                    category="account_health",
                    category_label="Account health",
                    count=2,
                    title="Payment holds",
                    tone="red",
                    href="/dashboard",
                ),
                _item(
                    id="low-inventory",
                    category="inventory",
                    category_label="Inventory",
                    count=12,
                    title="Low inventory SKUs",
                    tone="orange",
                    href="/dashboard",
                ),
                _item(
                    id="ad-budget",
                    category="advertising",
                    category_label="Advertising",
                    count=2,
                    title="Ad budget exhausted",
                    tone="purple",
                    href="/dashboard",
                ),
            ]
        )
        return items

    if user.kind == UserKind.EMPLOYEE:
        items.extend(
            [
                _item(
                    id="account-health-issues",
                    category="account_health",
                    category_label="Account health",
                    count=1,
                    title="Account health issues on assigned sellers",
                    tone="red",
                    href="/dashboard",
                ),
                _item(
                    id="policy-violation",
                    category="account_health",
                    category_label="Account health",
                    count=0,
                    title="Policy violations",
                    tone="red",
                    href="/dashboard",
                ),
                _item(
                    id="payment-hold",
                    category="account_health",
                    category_label="Account health",
                    count=1,
                    title="Payment holds",
                    tone="red",
                    href="/dashboard",
                ),
                _item(
                    id="low-inventory",
                    category="inventory",
                    category_label="Inventory",
                    count=5,
                    title="Low inventory on assigned sellers",
                    tone="orange",
                    href="/dashboard",
                ),
                _item(
                    id="ad-budget",
                    category="advertising",
                    category_label="Advertising",
                    count=1,
                    title="Ad budget exhausted",
                    tone="purple",
                    href="/dashboard",
                ),
            ]
        )
        return items

    # Seller portal
    items.extend(
        [
            _item(
                id="account-health-issues",
                category="account_health",
                category_label="Account health",
                count=1,
                title="Account health issues",
                tone="red",
                href="/dashboard",
            ),
            _item(
                id="policy-violation",
                category="account_health",
                category_label="Account health",
                count=0,
                title="Policy violations",
                tone="red",
                href="/dashboard",
            ),
            _item(
                id="payment-hold",
                category="account_health",
                category_label="Account health",
                count=1,
                title="Payment hold",
                tone="red",
                href="/dashboard",
            ),
            _item(
                id="low-inventory",
                category="inventory",
                category_label="Inventory",
                count=3,
                title="Low inventory SKUs",
                tone="orange",
                href="/dashboard",
            ),
            _item(
                id="ad-budget",
                category="advertising",
                category_label="Advertising",
                count=1,
                title="Ad budget exhausted",
                tone="purple",
                href="/dashboard",
            ),
        ]
    )
    return items


def alert_badge_count(db: Session, user: User) -> int:
    alerts = build_dashboard_alerts(db, user)
    total = sum(max(0, a["count"]) for a in alerts)
    if user.kind == UserKind.ADMIN:
        total += pending_access_request_count(db)
    return total
