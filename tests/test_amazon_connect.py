import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AmazonOAuthState, User, UserKind
from app.services.amazon.oauth_service import oauth_state_ttl
from tests.conftest import bearer_token

INDIA_MARKETPLACE = "A21TJRUUN4KGV"
CONNECT_PATH = "/api/amazon/connect"


def post_connect(client: TestClient, headers: dict[str, str] | None = None, body: dict | None = None):
    return client.post(
        CONNECT_PATH,
        json=body or {"marketplace_id": INDIA_MARKETPLACE},
        headers=headers,
    )


def test_unauthenticated_returns_401(client: TestClient) -> None:
    response = post_connect(client)
    assert response.status_code == 401


def test_admin_returns_200_and_authorization_url(client: TestClient, admin_user: User) -> None:
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "state" not in data
    assert settings.amazon_client_secret not in data["authorization_url"]
    assert "sellercentral.amazon.in" in data["authorization_url"]
    assert "application_id=" in data["authorization_url"]
    assert "version=beta" in data["authorization_url"]


def test_employee_with_connect_permission_returns_200(
    client: TestClient, employee_with_connect: User
) -> None:
    response = post_connect(client, headers=bearer_token(employee_with_connect.id))
    assert response.status_code == 200
    assert "authorization_url" in response.json()


def test_employee_without_connect_permission_returns_403(
    client: TestClient, employee_without_connect: User
) -> None:
    response = post_connect(client, headers=bearer_token(employee_without_connect.id))
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_seller_can_start_own_connect_flow(client: TestClient, seller_user: User) -> None:
    response = post_connect(client, headers=bearer_token(seller_user.id, UserKind.SELLER))
    assert response.status_code == 200
    assert "authorization_url" in response.json()


def test_oauth_state_stored_with_expiration(
    client: TestClient, admin_user: User, db: Session
) -> None:
    before = datetime.now(UTC)
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 200

    rows = db.execute(select(AmazonOAuthState)).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == admin_user.id
    assert row.marketplace_id == INDIA_MARKETPLACE
    assert row.used_at is None
    assert len(row.state) >= 32
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > before
    assert expires_at <= before + oauth_state_ttl() + timedelta(seconds=5)


def test_oauth_state_uses_secure_token(client: TestClient, admin_user: User) -> None:
    with patch(
        "app.services.amazon.oauth_service.generate_internal_oauth_state",
        return_value="mock-state",
    ):
        response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 200
    assert "state=mock-state" in response.json()["authorization_url"]


def test_oauth_state_token_length_in_authorization_url(
    client: TestClient, admin_user: User
) -> None:
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["authorization_url"]).query)
    state = query["state"][0]
    assert len(state) >= 32


def test_invalid_marketplace_id_returns_422(client: TestClient, admin_user: User) -> None:
    response = post_connect(
        client,
        headers=bearer_token(admin_user.id, UserKind.ADMIN),
        body={"marketplace_id": "not-valid"},
    )
    assert response.status_code == 422


def test_missing_marketplace_id_returns_422(client: TestClient, admin_user: User) -> None:
    response = client.post(
        CONNECT_PATH,
        json={},
        headers=bearer_token(admin_user.id, UserKind.ADMIN),
    )
    assert response.status_code == 422


def test_unsupported_marketplace_returns_400(client: TestClient, admin_user: User) -> None:
    response = post_connect(
        client,
        headers=bearer_token(admin_user.id, UserKind.ADMIN),
        body={"marketplace_id": "A1PA6795UKMFR9"},
    )
    assert response.status_code == 400
    assert "Unsupported marketplace_id" in response.json()["detail"]


def test_amazon_configuration_missing_returns_503(client: TestClient, admin_user: User) -> None:
    settings.amazon_app_id = None
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 503


def test_client_secret_never_in_response(client: TestClient, admin_user: User) -> None:
    settings.amazon_client_secret = "super-secret-value-xyz"
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert response.status_code == 200
    payload = response.text
    assert "super-secret-value-xyz" not in payload
    assert "client_secret" not in payload.lower()


def test_authorization_url_matches_sp_api_consent_pattern(
    client: TestClient, admin_user: User
) -> None:
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    url = response.json()["authorization_url"]
    assert re.match(
        r"^https://sellercentral\.amazon\.in/apps/authorize/consent\?"
        r"application_id=.+&state=.+&version=beta$",
        url,
    )


def test_draft_authorization_uri_includes_version_beta(
    client: TestClient, admin_user: User
) -> None:
    settings.amazon_authorize_version = "beta"
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    assert "version=beta" in response.json()["authorization_url"]


def test_published_authorization_uri_omits_version(
    client: TestClient, admin_user: User
) -> None:
    settings.amazon_authorize_version = ""
    response = post_connect(client, headers=bearer_token(admin_user.id, UserKind.ADMIN))
    url = response.json()["authorization_url"]
    assert "version=" not in url
    assert "/apps/authorize/consent?" in url
    assert "application_id=" in url
    assert "state=" in url
