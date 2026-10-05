from datetime import datetime

from pydantic import BaseModel, Field


class EmployeeProfileOut(BaseModel):
    id: str
    full_name: str
    employee_code: str | None = None
    location: str | None = None
    manager_name: str | None = None
    joined_at: datetime


class EmployeeSellerRowOut(BaseModel):
    id: str
    full_name: str
    status: str
    has_dashboard_access: bool
    access_request_status: str | None = None


class SellerAccessRequestOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    seller_id: str
    seller_name: str
    status: str
    created_at: datetime
