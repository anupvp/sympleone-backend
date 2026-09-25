from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    EmployeeSellerAssignment,
    GroupMember,
    GroupMemberKind,
    Policy,
    RolePolicy,
    User,
    UserKind,
    UserRole,
    UserStatus,
)

# Default policy codes (seeded)
POLICY_EMPLOYEES_MANAGE = "employees:manage"
POLICY_SELLERS_MANAGE = "sellers:manage"
POLICY_GROUPS_MANAGE = "groups:manage"
POLICY_ROLES_MANAGE = "roles:manage"
POLICY_SELLER_ACCOUNTS_READ = "seller_accounts:read"
POLICY_PRODUCTS_READ_OWN = "products:read_own"
POLICY_PRODUCTS_READ_ASSIGNED = "products:read_assigned"
POLICY_DASHBOARD_READ = "dashboard:read"

DEFAULT_POLICIES: list[tuple[str, str]] = [
    (POLICY_EMPLOYEES_MANAGE, "Create, update, suspend, delete employees"),
    (POLICY_SELLERS_MANAGE, "Manage seller accounts and assignments"),
    (POLICY_GROUPS_MANAGE, "Create and modify groups"),
    (POLICY_ROLES_MANAGE, "Manage roles and attach policies"),
    (POLICY_SELLER_ACCOUNTS_READ, "View all seller accounts"),
    (POLICY_PRODUCTS_READ_OWN, "View own products and services"),
    (POLICY_PRODUCTS_READ_ASSIGNED, "View products for assigned sellers"),
    (POLICY_DASHBOARD_READ, "View dashboard metrics"),
]


def user_policy_codes(db: Session, user: User) -> set[str]:
    if user.kind == UserKind.ADMIN:
        return {code for code, _ in DEFAULT_POLICIES}

    rows = db.execute(
        select(Policy.code)
        .join(RolePolicy, RolePolicy.policy_id == Policy.id)
        .join(UserRole, UserRole.role_id == RolePolicy.role_id)
        .where(UserRole.user_id == user.id)
    ).all()
    return {r[0] for r in rows}


def user_has_policy(db: Session, user: User, policy_code: str) -> bool:
    return policy_code in user_policy_codes(db, user)


def accessible_seller_ids(db: Session, user: User) -> set[str]:
    if user.kind == UserKind.ADMIN:
        sellers = db.execute(select(User.id).where(User.kind == UserKind.SELLER)).all()
        return {s[0] for s in sellers}

    if user.kind == UserKind.SELLER:
        return {user.id}

    if user.kind != UserKind.EMPLOYEE:
        return set()

    direct = db.execute(
        select(EmployeeSellerAssignment.seller_id).where(
            EmployeeSellerAssignment.employee_id == user.id
        )
    ).all()
    employee_groups = db.execute(
        select(GroupMember.group_id).where(
            GroupMember.user_id == user.id,
            GroupMember.member_kind == GroupMemberKind.EMPLOYEE,
        )
    ).all()
    group_ids = [g[0] for g in employee_groups]
    group_sellers: set[str] = set()
    if group_ids:
        rows = db.execute(
            select(GroupMember.user_id).where(
                GroupMember.group_id.in_(group_ids),
                GroupMember.member_kind == GroupMemberKind.SELLER,
            )
        ).all()
        group_sellers = {r[0] for r in rows}

    return {r[0] for r in direct} | group_sellers


def assert_user_active(user: User) -> None:
    if user.status != UserStatus.ACTIVE:
        raise PermissionError("Account is suspended")
