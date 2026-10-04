from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EmployeeSellerAssignment, User, UserKind
from tests.conftest import bearer_token


def test_sellers_overview_for_admin(
    client: TestClient,
    db: Session,
    admin_user: User,
) -> None:
    paid = User(
        email="paid@test.com",
        full_name="Paid Seller",
        hashed_password="x",
        kind=UserKind.SELLER,
        is_paid=True,
    )
    unpaid = User(
        email="unpaid@test.com",
        full_name="Unpaid Seller",
        hashed_password="x",
        kind=UserKind.SELLER,
        is_paid=False,
    )
    db.add_all([paid, unpaid])
    db.commit()
    db.refresh(paid)
    db.refresh(unpaid)

    employee = User(
        email="emp@test.com",
        full_name="Employee",
        hashed_password="x",
        kind=UserKind.EMPLOYEE,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)

    db.add(
        EmployeeSellerAssignment(employee_id=employee.id, seller_id=paid.id),
    )
    db.commit()

    response = client.get(
        "/api/admin/sellers/overview",
        headers=bearer_token(admin_user.id, admin_user.kind),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["total"] == 2
    assert data["counts"]["paid"] == 1
    assert data["counts"]["unpaid"] == 1
    assert data["counts"]["assigned"] == 1
    assert data["counts"]["unassigned"] == 1
