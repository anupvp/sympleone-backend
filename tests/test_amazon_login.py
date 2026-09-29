import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AmazonAppstoreOAuthSession
from app.services.amazon.oauth_service import oauth_state_ttl
from tests.conftest import bearer_token

LOGIN_PATH = "/api/amazon/login"
VALID_CALLBACK = (
    "https://sellercentral.amazon.com/apps/authorize/confirm/"
    "amzn1.sellerapps.app.test?redirect_uri=https%3A%2F%2Fexample.com"
)
AMAZON_STATE = "amazon-state-from-amazon-xyz"
PARTNER_ID = "A3Q9EXAMPLEID"


def login_get(client: TestClient, **params: str):
    return client.get(LOGIN_PATH, params=params, follow_redirects=False)


def test_missing_amazon_callback_uri_returns_400(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400
    assert "amazon_callback_uri" in response.json()["detail"]


def test_missing_amazon_state_returns_400(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400
    assert "amazon_state" in response.json()["detail"]


def test_missing_selling_partner_id_returns_400(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
    )
    assert response.status_code == 400
    assert "selling_partner_id" in response.json()["detail"]


def test_http_callback_uri_rejected(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri="http://sellercentral.amazon.com/apps/authorize/confirm/x",
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_javascript_callback_uri_rejected(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri="javascript:alert(1)",
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_non_amazon_callback_host_rejected(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri="https://evil.example.com/steal",
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 400


def test_invalid_selling_partner_id_returns_400(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id="not-valid!",
    )
    assert response.status_code == 400


def test_both_states_persisted_exactly(client: TestClient, db: Session) -> None:
    exact_amazon_state = "amazon-state+with/special=chars&more"
    with patch(
        "app.services.amazon.appstore_login_service.generate_internal_oauth_state",
        return_value="symple-fixed-internal-state",
    ):
        response = login_get(
            client,
            amazon_callback_uri=VALID_CALLBACK,
            amazon_state=exact_amazon_state,
            selling_partner_id=PARTNER_ID,
        )
    assert response.status_code == 302
    row = db.execute(select(AmazonAppstoreOAuthSession)).scalar_one()
    assert row.amazon_state == exact_amazon_state
    assert row.internal_state == "symple-fixed-internal-state"
    assert row.amazon_state != row.internal_state
    assert row.selling_partner_id == PARTNER_ID
    assert row.amazon_callback_uri == VALID_CALLBACK


def test_amazon_state_preserved_exactly_on_redirect(client: TestClient) -> None:
    exact_state = "amazon-state+with/special=chars&more"
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=exact_state,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["amazon_state"] == [exact_state]


def test_redirect_uri_is_configured_symple_callback(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["redirect_uri"] == [settings.amazon_redirect_uri]


def test_redirect_preserves_other_callback_query_params(client: TestClient) -> None:
    callback = (
        "https://sellercentral.amazon.com/apps/authorize/confirm/"
        "amzn1.sellerapps.app.test?version=beta&foo=bar"
    )
    response = login_get(
        client,
        amazon_callback_uri=callback,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert query["version"] == ["beta"]
    assert query["foo"] == ["bar"]
    assert query["redirect_uri"] == [settings.amazon_redirect_uri]


def test_redirect_state_matches_stored_symple_state(client: TestClient, db: Session) -> None:
    with patch(
        "app.services.amazon.appstore_login_service.generate_internal_oauth_state",
        return_value="symple-state-for-redirect-test",
    ):
        response = login_get(
            client,
            amazon_callback_uri=VALID_CALLBACK,
            amazon_state=AMAZON_STATE,
            selling_partner_id=PARTNER_ID,
        )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["state"] == ["symple-state-for-redirect-test"]
    row = db.execute(select(AmazonAppstoreOAuthSession)).scalar_one()
    assert row.internal_state == query["state"][0]


def test_redirect_targets_supplied_amazon_callback_uri(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    expected = urlparse(VALID_CALLBACK)
    assert location.scheme == expected.scheme
    assert location.netloc == expected.netloc
    assert location.path == expected.path


def test_missing_amazon_redirect_uri_returns_503(client: TestClient) -> None:
    settings.amazon_redirect_uri = None
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 503


def test_valid_request_redirects_to_amazon_callback(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://sellercentral.amazon.com/")
    query = parse_qs(urlparse(location).query)
    assert query["amazon_state"] == [AMAZON_STATE]
    assert "state" in query
    assert len(query["state"][0]) >= 32


def test_oauth_session_persisted_with_expiration(client: TestClient, db: Session) -> None:
    before = datetime.now(UTC)
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302
    internal_state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]

    row = db.execute(
        select(AmazonAppstoreOAuthSession).where(
            AmazonAppstoreOAuthSession.internal_state == internal_state
        )
    ).scalar_one()
    assert row.amazon_state == AMAZON_STATE
    assert row.selling_partner_id == PARTNER_ID
    assert row.amazon_callback_uri == VALID_CALLBACK
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    assert expires > before
    assert expires <= before + oauth_state_ttl() + timedelta(seconds=5)


def test_two_login_requests_generate_different_internal_states(client: TestClient) -> None:
    r1 = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    r2 = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    s1 = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    s2 = parse_qs(urlparse(r2.headers["location"]).query)["state"][0]
    assert s1 != s2


def test_sensitive_values_not_logged(client: TestClient) -> None:
    with patch("app.services.amazon.appstore_login_service.logger.info") as log_info:
        with patch(
            "app.services.amazon.oauth_state.generate_internal_oauth_state",
            return_value="internal-secret-state-value",
        ):
            login_get(
                client,
                amazon_callback_uri=VALID_CALLBACK,
                amazon_state="super-secret-amazon-state",
                selling_partner_id=PARTNER_ID,
            )
    assert log_info.call_count == 1
    log_args = str(log_info.call_args)
    assert "super-secret-amazon-state" not in log_args
    assert "internal-secret-state-value" not in log_args


def test_unauthenticated_login_still_redirects(client: TestClient) -> None:
    response = login_get(
        client,
        amazon_callback_uri=VALID_CALLBACK,
        amazon_state=AMAZON_STATE,
        selling_partner_id=PARTNER_ID,
    )
    assert response.status_code == 302


def test_existing_auth_api_unchanged(client: TestClient) -> None:
    assert client.post("/api/auth/login", json={}).status_code == 422
