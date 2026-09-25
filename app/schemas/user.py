from pydantic import BaseModel, EmailStr, Field

from app.models import UserKind, UserStatus


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role_ids: list[str] = Field(default_factory=list)


class EmployeeUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role_ids: list[str] | None = None


class SellerCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)


class SellerUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    kind: UserKind
    status: UserStatus
    role_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}
