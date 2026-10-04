from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.secret_storage import encrypt_secret
from app.models import AmazonConnectionStatus, AmazonSellerAuthorization, User
from tests.conftest import bearer_token


def _link_seller_amazon(db: Session, seller: User) -> None:
    row = AmazonSellerAuthorization(
        selling_partner_id="A3Q9EXAMPLEID",
        user_id=seller.id,
        organization_id=None,
        refresh_token_ciphertext=encrypt_secret("refresh-token-test"),
        status=AmazonConnectionStatus.ACTIVE,
    )
    db.add(row)
    db.commit()


@patch("app.services.dashboard.stats_service.fetch_order_metrics")
@patch("app.services.dashboard.stats_service.refresh_lwa_access_token")
def test_dashboard_stats_gmv_for_seller(
    mock_refresh,
    mock_metrics,
    client: TestClient,
    db: Session,
    seller_user: User,
) -> None:
    mock_refresh.return_value = "lwa-access-token"
    mock_metrics.side_effect = [
        ({"2026-09-01": 4_860_000.0}, {}, "INR"),
        ({"2026-08-01": 4_320_000.0}, {}, "INR"),
    ]
    _link_seller_amazon(db, seller_user)

    response = client.get(
        "/api/dashboard/stats",
        headers=bearer_token(seller_user.id, seller_user.kind),
        params={
            "marketplaceId": "A21TJRUUN4KGV",
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-30",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    card = data[0]
    assert card["id"] == "gmv"
    assert card["label"] == "SALES"
    assert card["value"] == "₹48.6L"
    assert card["icon"] == "gmv"
    assert card["changePercent"] == 12.5


def test_dashboard_stats_requires_amazon_connection(
    client: TestClient,
    seller_user: User,
) -> None:
    response = client.get(
        "/api/dashboard/stats",
        headers=bearer_token(seller_user.id, seller_user.kind),
    )
    assert response.status_code == 400
    assert "Connect your Amazon" in response.json()["detail"]
