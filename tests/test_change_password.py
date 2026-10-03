from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User
from tests.conftest import bearer_token


def test_change_password_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "password", "new_password": "newpass1"},
    )
    assert response.status_code == 401


def test_change_password_wrong_current(
    client: TestClient,
    seller_user: User,
) -> None:
    headers = bearer_token(seller_user.id, seller_user.kind)
    response = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "newpass1"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_change_password_same_as_current(
    client: TestClient,
    seller_user: User,
) -> None:
    headers = bearer_token(seller_user.id, seller_user.kind)
    response = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "password", "new_password": "password"},
    )
    assert response.status_code == 400
    assert "different" in response.json()["detail"].lower()


def test_seller_can_change_password(
    client: TestClient,
    db: Session,
    seller_user: User,
) -> None:
    headers = bearer_token(seller_user.id, seller_user.kind)
    response = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "password", "new_password": "newpass9"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated"

    db.refresh(seller_user)
    assert verify_password("newpass9", seller_user.hashed_password)
    assert not verify_password("password", seller_user.hashed_password)

    login = client.post(
        "/api/auth/login",
        json={"email": seller_user.email, "password": "newpass9"},
    )
    assert login.status_code == 200
