from fastapi.testclient import TestClient


def test_privacy_returns_200(client: TestClient) -> None:
    response = client.get("/privacy")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "privacy"
    assert data["title"] == "Privacy Policy"
    assert len(data["sections"]) >= 1


def test_terms_returns_200(client: TestClient) -> None:
    response = client.get("/terms")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "terms"
    assert data["title"] == "Terms of Service"


def test_support_returns_200_and_contact(client: TestClient) -> None:
    response = client.get("/support")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "support"
    assert data["contact_email"] == "support@sympleone.com"
