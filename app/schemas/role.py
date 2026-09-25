from pydantic import BaseModel, Field


class PolicyOut(BaseModel):
    id: str
    code: str
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    policy_ids: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    policy_ids: list[str] | None = None


class RoleOut(BaseModel):
    id: str
    name: str
    description: str | None
    policy_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AttachRolesRequest(BaseModel):
    role_ids: list[str] = Field(min_length=1)
