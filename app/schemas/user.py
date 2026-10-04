from pydantic import BaseModel, EmailStr, Field

from app.models import UserKind, UserStatus


class AssignedSellerSummary(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    status: UserStatus


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role_ids: list[str] = Field(default_factory=list)
    seller_ids: list[str] = Field(default_factory=list)


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
    is_paid: bool | None = None


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    kind: UserKind
    status: UserStatus
    role_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SellerOut(UserOut):
    is_paid: bool = False
    is_assigned: bool = False
    assigned_employees: list[str] = Field(default_factory=list)


class AdminSellersOverviewOut(BaseModel):
    counts: dict[str, int]
    sellers: list[SellerOut]


class EmployeeOut(UserOut):
    assigned_sellers: list[AssignedSellerSummary] = Field(default_factory=list)
