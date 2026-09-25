from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Policy, Role, RolePolicy, User, UserKind, UserRole
from app.schemas.role import AttachRolesRequest, PolicyOut, RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/admin", tags=["admin-rbac"])


def _role_out(db: Session, role: Role) -> RoleOut:
    ids = db.execute(select(RolePolicy.policy_id).where(RolePolicy.role_id == role.id)).all()
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        policy_ids=[r[0] for r in ids],
    )


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[PolicyOut]:
    return db.execute(select(Policy)).scalars().all()


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[RoleOut]:
    roles = db.execute(select(Role)).scalars().all()
    return [_role_out(db, r) for r in roles]


def _sync_role_policies(db: Session, role: Role, policy_ids: list[str]) -> None:
    policies = db.execute(select(Policy).where(Policy.id.in_(policy_ids))).scalars().all()
    if len(policies) != len(set(policy_ids)):
        raise HTTPException(status_code=400, detail="One or more policies not found")
    db.query(RolePolicy).filter(RolePolicy.role_id == role.id).delete()
    for p in policies:
        db.add(RolePolicy(role_id=role.id, policy_id=p.id))


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    body: RoleCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RoleOut:
    if db.execute(select(Role.id).where(Role.name == body.name)).first():
        raise HTTPException(status_code=409, detail="Role name exists")
    role = Role(name=body.name, description=body.description)
    db.add(role)
    db.flush()
    if body.policy_ids:
        _sync_role_policies(db, role, body.policy_ids)
    db.commit()
    db.refresh(role)
    return _role_out(db, role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: str,
    body: RoleUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RoleOut:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if body.name and body.name != role.name:
        if db.execute(select(Role.id).where(Role.name == body.name)).first():
            raise HTTPException(status_code=409, detail="Role name exists")
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.policy_ids is not None:
        _sync_role_policies(db, role, body.policy_ids)
    db.commit()
    db.refresh(role)
    return _role_out(db, role)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(role)
    db.commit()


@router.post("/employees/{employee_id}/roles", response_model=list[str])
def attach_roles_to_employee(
    employee_id: str,
    body: AttachRolesRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[str]:
    employee = db.get(User, employee_id)
    if not employee or employee.kind != UserKind.EMPLOYEE:
        raise HTTPException(status_code=404, detail="Employee not found")
    roles = db.execute(select(Role).where(Role.id.in_(body.role_ids))).scalars().all()
    if len(roles) != len(set(body.role_ids)):
        raise HTTPException(status_code=400, detail="Invalid role ids")
    for role in roles:
        exists = db.execute(
            select(UserRole.id).where(
                UserRole.user_id == employee_id,
                UserRole.role_id == role.id,
            )
        ).first()
        if not exists:
            db.add(UserRole(user_id=employee_id, role_id=role.id))
    db.commit()
    rows = db.execute(select(UserRole.role_id).where(UserRole.user_id == employee_id)).all()
    return [r[0] for r in rows]
