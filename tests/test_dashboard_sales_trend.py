from datetime import date
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


@patch("app.services.dashboard.sales_trend_service.fetch_order_metrics")
@patch("app.services.dashboard.sales_trend_service.refresh_lwa_access_token")
def test_sales_trend_for_seller(
    mock_refresh,
    mock_metrics,
    client: TestClient,
    db: Session,
    seller_user: User,
) -> None:
    mock_refresh.return_value = "lwa-access-token"
    mock_metrics.side_effect = [
        (
            {"2026-09-01": 500_000.0, "2026-09-02": 700_000.0},
            "INR",
        ),
        (
            {"2026-08-01": 400_000.0, "2026-08-02": 450_000.0},
            "INR",
        ),
    ]
    _link_seller_amazon(db, seller_user)

    response = client.get(
        "/api/dashboard/sales-trend",
        headers=bearer_token(seller_user.id, seller_user.kind),
        params={
            "marketplaceId": "A21TJRUUN4KGV",
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-02",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["currencySymbol"] == "₹"
    assert len(data["points"]) == 2
    assert data["points"][0]["netSales"] == 5.0
    assert data["points"][0]["previousPeriod"] == 4.0


def test_sales_trend_requires_amazon_connection(
    client: TestClient,
    seller_user: User,
) -> None:
    response = client.get(
        "/api/dashboard/sales-trend",
        headers=bearer_token(seller_user.id, seller_user.kind),
    )
    assert response.status_code == 400
    assert "Connect your Amazon" in response.json()["detail"]


@patch("app.services.amazon.sales_order_metrics.sp_api_get")
def test_order_metrics_interval_and_host(mock_get) -> None:
    from app.services.amazon.sales_order_metrics import fetch_order_metrics

    mock_get.return_value = {
        "payload": [
            {
                "interval": "2026-09-01T00:00:00Z--2026-09-01T23:59:59Z",
                "totalSales": {"currencyCode": "INR", "amount": "1000.50"},
            }
        ]
    }

    buckets, currency = fetch_order_metrics(
        access_token="token",
        marketplace_id="A21TJRUUN4KGV",
        start=date(2026, 9, 1),
        end=date(2026, 9, 30),
        granularity="Day",
    )
    assert currency == "INR"
    assert buckets["2026-09-01"] == 1000.50
    called_url_host = mock_get.call_args.kwargs["host"]
    assert called_url_host == "sellingpartnerapi-eu.amazon.com"
