from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class AuthUserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    accessToken: str
    user: AuthUserOut


class MeResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    status: str
    policies: list[str]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class ChangePasswordResponse(BaseModel):
    message: str
