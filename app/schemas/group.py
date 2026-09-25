from pydantic import BaseModel, Field

from app.models.group import GroupMemberKind


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    employee_ids: list[str] = Field(default_factory=list)
    seller_ids: list[str] = Field(default_factory=list)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    employee_ids: list[str] | None = None
    seller_ids: list[str] | None = None


class GroupMemberOut(BaseModel):
    user_id: str
    member_kind: GroupMemberKind
    email: str
    full_name: str


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None
    members: list[GroupMemberOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AssignSellersRequest(BaseModel):
    seller_ids: list[str] = Field(min_length=1)
