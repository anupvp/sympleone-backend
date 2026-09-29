from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.secret_storage import decrypt_secret
from app.models import (
    AmazonAppstoreOAuthSession,
    AmazonConnectionStatus,
    AmazonSellerAuthorization,
    User,
)
from app.services.amazon.oauth_state import oauth_state_expires_at

CALLBACK_PATH = "/api/amazon/callback"
PARTNER_ID = "A3Q9EXAMPLEID"
CODE = "Atza|SpApiAuthCodeExample"


def callback_get(client: TestClient, **params: str):
    return client.get(CALLBACK_PATH, params=params, follow_redirects=False)


def seed_session(
    db: Session,
    *,
    internal_state: str = "test-internal-state-token",
    selling_partner_id: str = PARTNER_ID,
    expired: bool = False,
    used: bool = False,
    user_id: str | None = None,
) -> AmazonAppstoreOAuthSession:
    now = datetime.now(UTC)
    expires = now - timedelta(minutes=1) if expired else oauth_state_expires_at(now)
    row = AmazonAppstoreOAuthSession(
        internal_state=internal_state,
        amazon_state="amazon-state",
        selling_partner_id=selling_partner_id,
        amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm/x",
        user_id=user_id,
        organization_id=None,
        expires_at=expires,
        used_at=now if used else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture(autouse=True)
def _lwa_env() -> None:
    settings.amazon_client_id = "amzn1.application-oa2-client.test"
    settings.amazon_client_secret = "test-client-secret"
    settings.amazon_redirect_uri = "https://api.example.com/api/amazon/callback"
    settings.amazon_oauth_success_redirect_url = "https://app.example.com/dashboard"


def test_missing_spapi_oauth_code_returns_400(client: TestClient, db: Session) -> None:
    seed_session(db)
    response = callback_get(
        client,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_missing_state_returns_400(client: TestClient) -> None:
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_missing_selling_partner_id_returns_400(client: TestClient, db: Session) -> None:
    seed_session(db)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
    )
    assert response.status_code == 400


def test_invalid_state_returns_400(client: TestClient) -> None:
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="unknown-state",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_expired_state_returns_400(client: TestClient, db: Session) -> None:
    seed_session(db, expired=True)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_already_used_state_returns_400(client: TestClient, db: Session) -> None:
    seed_session(db, used=True)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_seller_mismatch_returns_400(client: TestClient, db: Session) -> None:
    seed_session(db)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id="A3OTHERSELLER1",
    )
    assert response.status_code == 400


@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_callback_persists_user_id_from_oauth_session(
    mock_exchange,
    client: TestClient,
    db: Session,
    admin_user: User,
) -> None:
    mock_exchange.return_value = {
        "access_token": "secret-access",
        "refresh_token": "secret-refresh",
        "expires_in": 3600,
    }
    seed_session(db, user_id=admin_user.id)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    auth = db.execute(
        select(AmazonSellerAuthorization).where(
            AmazonSellerAuthorization.selling_partner_id == PARTNER_ID
        )
    ).scalar_one()
    assert auth.user_id == admin_user.id


@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_authorization_code_passed_only_to_token_exchange(
    mock_exchange,
    client: TestClient,
    db: Session,
) -> None:
    mock_exchange.return_value = {
        "access_token": "secret-access",
        "refresh_token": "secret-refresh",
        "expires_in": 3600,
    }
    seed_session(db)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    mock_exchange.assert_called_once_with(CODE)
    assert CODE not in (response.headers.get("location") or "")
    assert CODE not in response.text


@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_successful_callback_redirects_and_persists(
    mock_exchange,
    client: TestClient,
    db: Session,
) -> None:
    mock_exchange.return_value = {
        "access_token": "secret-access",
        "refresh_token": "secret-refresh",
        "token_type": "bearer",
        "expires_in": 3600,
    }
    seed_session(db, user_id=None)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://app.example.com/dashboard")
    assert "amazon=connected" in response.headers["location"]
    assert "secret-refresh" not in response.text

    auth = db.execute(
        select(AmazonSellerAuthorization).where(
            AmazonSellerAuthorization.selling_partner_id == PARTNER_ID
        )
    ).scalar_one()
    assert decrypt_secret(auth.refresh_token_ciphertext) == "secret-refresh"
    assert auth.status == AmazonConnectionStatus.ACTIVE
    assert auth.connected_at is not None
    assert auth.last_authorized_at is not None

    session = db.execute(
        select(AmazonAppstoreOAuthSession).where(
            AmazonAppstoreOAuthSession.internal_state == "test-internal-state-token"
        )
    ).scalar_one()
    assert session.used_at is not None


@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_token_exchange_failure_redirects_to_error(mock_exchange, client: TestClient, db: Session) -> None:
    from app.services.amazon.lwa_token_service import LwaTokenExchangeError

    mock_exchange.side_effect = LwaTokenExchangeError("failed")
    seed_session(db)
    response = callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    assert "amazon=error" in response.headers["location"]


@patch("app.services.amazon.callback_service.logger.info")
@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_callback_does_not_log_state_or_auth_code(
    mock_exchange,
    log_info,
    client: TestClient,
    db: Session,
) -> None:
    mock_exchange.return_value = {"refresh_token": "rt1", "access_token": "a", "expires_in": 1}
    seed_session(db)
    callback_get(
        client,
        spapi_oauth_code=CODE,
        state="test-internal-state-token",
        selling_partner_id=PARTNER_ID,
    )
    logged = str(log_info.call_args_list)
    assert CODE not in logged
    assert "test-internal-state-token" not in logged


@patch("app.services.amazon.callback_service.exchange_authorization_code")
def test_state_cannot_be_reused(mock_exchange, client: TestClient, db: Session) -> None:
    mock_exchange.return_value = {"refresh_token": "rt1", "access_token": "a", "expires_in": 1}
    seed_session(db)
    params = {
        "spapi_oauth_code": CODE,
        "state": "test-internal-state-token",
        "selling_partner_id": PARTNER_ID,
    }
    assert callback_get(client, **params).status_code == 302
    response = callback_get(client, **params)
    assert response.status_code == 400
