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


@patch("app.services.dashboard.stats_service.build_active_products_metrics")
@patch("app.services.dashboard.stats_service.compute_net_profit")
@patch("app.services.dashboard.stats_service.fetch_orders")
@patch("app.services.dashboard.stats_service.fetch_order_metrics")
@patch("app.services.dashboard.stats_service.refresh_lwa_access_token")
def test_dashboard_stats_gmv_for_seller(
    mock_refresh,
    mock_metrics,
    mock_orders,
    mock_net_profit,
    mock_active_products,
    client: TestClient,
    db: Session,
    seller_user: User,
) -> None:
    mock_refresh.return_value = "lwa-access-token"
    mock_metrics.side_effect = [
        ({"2026-09-01": 4_860_000.0}, {}, "INR"),
        ({"2026-08-01": 4_320_000.0}, {}, "INR"),
    ]
    mock_orders.side_effect = [
        [
            {"OrderStatus": "Shipped", "AmazonOrderId": "1"},
            {"OrderStatus": "Shipped", "AmazonOrderId": "2"},
            {"OrderStatus": "Canceled", "AmazonOrderId": "3"},
        ],
        [{"OrderStatus": "Shipped", "AmazonOrderId": "4"}],
    ]
    mock_net_profit.side_effect = [
        (248_910.0, 20.0, "INR"),
        (216_000.0, 18.0, "INR"),
    ]
    mock_active_products.return_value = (89, 3, 2, 5)
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
    assert len(data) == 4
    gmv = data[0]
    assert gmv["id"] == "gmv"
    assert gmv["label"] == "SALES"
    assert gmv["value"] == "₹48.6L"
    assert gmv["icon"] == "gmv"
    assert gmv["changePercent"] == 12.5
    orders = data[1]
    assert orders["id"] == "net-sales"
    assert orders["value"] == "2"
    assert orders["changePercent"] == 100.0
    profit = data[2]
    assert profit["id"] == "profit"
    assert profit["label"] == "Net Profit"
    assert profit["value"] == "₹2.5L"
    assert profit["subline"] == "20.0% margin"
    assert profit["changePercent"] == 15.2
    active = data[3]
    assert active["id"] == "profit-pct"
    assert active["label"] == "Active Products"
    assert active["value"] == "89"
    assert active["subline"] == "5 low in stock"
    assert active["changePercent"] == 50.0


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
