from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserKind


def test_public_seller_count(
    client: TestClient,
    db: Session,
) -> None:
    db.add_all(
        [
            User(
                email="s1@test.com",
                full_name="S One",
                hashed_password="x",
                kind=UserKind.SELLER,
            ),
            User(
                email="s2@test.com",
                full_name="S Two",
                hashed_password="x",
                kind=UserKind.SELLER,
            ),
        ]
    )
    db.commit()

    response = client.get("/api/public/seller-count")
    assert response.status_code == 200
    assert response.json() == {"total": 2}
