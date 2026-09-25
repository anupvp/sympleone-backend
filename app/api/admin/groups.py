from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Group, GroupMember, GroupMemberKind, User, UserKind
from app.schemas.group import GroupCreate, GroupOut, GroupUpdate

router = APIRouter(prefix="/admin/groups", tags=["admin-groups"])


def _group_to_out(db: Session, group: Group) -> GroupOut:
    members_out = []
    for m in group.members:
        u = db.get(User, m.user_id)
        if u:
            members_out.append(
                {
                    "user_id": u.id,
                    "member_kind": m.member_kind,
                    "email": u.email,
                    "full_name": u.full_name,
                }
            )
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        members=members_out,
    )


def _sync_members(
    db: Session,
    group: Group,
    employee_ids: list[str],
    seller_ids: list[str],
) -> None:
    db.query(GroupMember).filter(GroupMember.group_id == group.id).delete()
    for eid in employee_ids:
        user = db.get(User, eid)
        if not user or user.kind != UserKind.EMPLOYEE:
            raise HTTPException(status_code=400, detail=f"Invalid employee: {eid}")
        db.add(GroupMember(group_id=group.id, user_id=eid, member_kind=GroupMemberKind.EMPLOYEE))
    for sid in seller_ids:
        user = db.get(User, sid)
        if not user or user.kind != UserKind.SELLER:
            raise HTTPException(status_code=400, detail=f"Invalid seller: {sid}")
        db.add(GroupMember(group_id=group.id, user_id=sid, member_kind=GroupMemberKind.SELLER))


@router.get("", response_model=list[GroupOut])
def list_groups(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[GroupOut]:
    groups = db.execute(select(Group)).scalars().all()
    return [_group_to_out(db, g) for g in groups]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GroupOut:
    exists = db.execute(select(Group.id).where(Group.name == body.name)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Group name already exists")
    group = Group(name=body.name, description=body.description)
    db.add(group)
    db.flush()
    _sync_members(db, group, body.employee_ids, body.seller_ids)
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: str,
    body: GroupUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if body.name and body.name != group.name:
        clash = db.execute(select(Group.id).where(Group.name == body.name)).first()
        if clash:
            raise HTTPException(status_code=409, detail="Group name already exists")
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    if body.employee_ids is not None or body.seller_ids is not None:
        emp = body.employee_ids if body.employee_ids is not None else [
            m.user_id for m in group.members if m.member_kind == GroupMemberKind.EMPLOYEE
        ]
        sel = body.seller_ids if body.seller_ids is not None else [
            m.user_id for m in group.members if m.member_kind == GroupMemberKind.SELLER
        ]
        _sync_members(db, group, emp, sel)
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
